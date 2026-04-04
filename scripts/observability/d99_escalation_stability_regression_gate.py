#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D99 escalation stability regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D99 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D99 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        _fail(f"D99 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                _fail(f"D99 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D99 invalid escalation CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D99 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        _fail(f"D99 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--status-field", default="status")
    parser.add_argument("--stability-field", default="stability_score")
    parser.add_argument("--max-stability-regressions", type=int, default=0)
    parser.add_argument("--max-stability-drop", type=float, default=0.0)
    parser.add_argument("--max-stability-variance", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _read_json(report_path)
    rows = _read_csv(
        csv_path, {args.time_field, args.status_field, args.stability_field}
    )
    if not rows:
        _fail("D99 escalation stability regression gate failed: empty escalation csv")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or "").strip())
    stability = [
        _to_float(row.get(args.stability_field, ""), csv_path, args.stability_field)
        for row in ordered
        if (row.get(args.status_field) or "").strip().lower() in {"open", "active", "in_progress"}
    ]

    if len(stability) < 2:
        _fail("D99 escalation stability regression gate failed: insufficient stability points")

    regressions = _to_int(
        str(report.get("escalation_stability_regressions", 0)),
        report_path,
        "escalation_stability_regressions",
    )
    max_drop = 0.0
    for prior, current in zip(stability, stability[1:]):
        drop = prior - current
        if drop > 0:
            max_drop = max(max_drop, drop)
            regressions += 1

    report_drop = float(report.get("escalation_stability_drop", 0.0))
    if max_drop < report_drop:
        max_drop = report_drop

    if len(stability) > 1:
        mean = sum(stability) / len(stability)
        variance = sum((value - mean) ** 2 for value in stability) / len(stability)
    else:
        variance = 0.0

    if max_drop > args.max_stability_drop:
        _fail(f"D99 escalation stability regression gate failed: max_drop={max_drop}")
    if regressions > args.max_stability_regressions:
        _fail(f"D99 escalation stability regression gate failed: regressions={regressions}")
    if variance > args.max_stability_variance:
        _fail(f"D99 escalation stability regression gate failed: variance={variance}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

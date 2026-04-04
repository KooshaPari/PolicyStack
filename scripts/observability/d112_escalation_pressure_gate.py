#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D112 escalation pressure gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D112 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D112 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D112 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D112 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D112 invalid escalation CSV {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        fail(f"D112 invalid {field} in {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D112 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--severity-field", default="severity")
    parser.add_argument("--count-field", default="open_escalations")
    parser.add_argument("--max-open-escalations", type=int, default=0)
    parser.add_argument("--max-severe-spike", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _read_json(report_path)
    rows = _read_csv(
        csv_path, {args.time_field, args.severity_field, args.count_field}
    )
    if not rows:
        fail("D112 escalation pressure gate failed: empty escalation data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    severe_counts: list[int] = []
    for row in ordered:
        severity = (row.get(args.severity_field) or "").strip().lower()
        if severity in {"sev1", "sev2"}:
            severe_counts.append(
                _to_int(row.get(args.count_field, ""), csv_path, args.count_field)
            )

    if not severe_counts:
        fail("D112 escalation pressure gate failed: no severe escalations observed")

    max_open = max(severe_counts)
    report_open = int(report.get("escalation_severe_open", 0))
    if max_open < report_open:
        max_open = report_open

    if len(severe_counts) > 1:
        spikes = [float(abs(a - b)) for a, b in zip(severe_counts, severe_counts[1:])]
        max_spike = max(spikes)
    else:
        max_spike = 0.0
    report_spike = float(report.get("escalation_severe_spike", 0.0))
    if max_spike < report_spike:
        max_spike = report_spike

    if max_open > args.max_open_escalations:
        fail(f"D112 max_open_escalations={max_open} > max_open_escalations={args.max_open_escalations}")
    if max_spike > args.max_severe_spike:
        fail(f"D112 max_severe_spike={max_spike} > max_severe_spike={args.max_severe_spike}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

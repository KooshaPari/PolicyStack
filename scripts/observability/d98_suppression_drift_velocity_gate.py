#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D98 suppression drift velocity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D98 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D98 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        _fail(f"D98 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                _fail(f"D98 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D98 invalid suppression CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D98 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        _fail(f"D98 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--value-field", default="suppression_drift")
    parser.add_argument("--velocity-threshold", type=float, default=0.0)
    parser.add_argument("--max-velocity", type=float, default=0.0)
    parser.add_argument("--max-velocity-breaches", type=int, default=0)
    parser.add_argument("--status-field", default="status")
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppression_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppression")

    report = _load_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field, args.status_field})
    if not rows:
        _fail("D98 suppression drift velocity gate failed: empty suppression csv")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or "").strip())
    values = [_to_float(row.get(args.value_field, ""), csv_path, args.value_field) for row in ordered]

    velocities = []
    for prior, current in zip(values, values[1:]):
        velocities.append(abs(current - prior))

    max_velocity = max(velocities) if velocities else 0.0
    report_velocity = float(report.get("suppression_drift_velocity", 0.0))
    if max_velocity < report_velocity:
        max_velocity = report_velocity

    breaches = _to_int(
        str(report.get("suppression_drift_velocity_breaches", 0)),
        report_path,
        "suppression_drift_velocity_breaches",
    )
    for velocity in velocities:
        if velocity > args.velocity_threshold:
            breaches += 1

    if max_velocity > args.max_velocity:
        _fail(f"D98 suppression drift velocity gate failed: max_velocity={max_velocity}")
    if breaches > args.max_velocity_breaches:
        _fail(f"D98 suppression drift velocity gate failed: velocity_breaches={breaches}")
    if args.velocity_threshold <= 0 and report.get("suppression_drift_velocity_peak", 0.0) > args.max_velocity:
        _fail(
            "D98 suppression drift velocity gate failed: "
            f"report_peak={report.get('suppression_drift_velocity_peak', 0.0)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

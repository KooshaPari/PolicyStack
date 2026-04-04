#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D109 override recovery gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D109 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D109 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D109 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D109 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D109 invalid override CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D109 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        fail(f"D109 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--open-field", default="open_overrides")
    parser.add_argument("--recovery-field", default="recovery_time")
    parser.add_argument("--max-open-overrides", type=int, default=0)
    parser.add_argument("--max-recovery-time", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.open_field, args.recovery_field})
    if not rows:
        fail("D109 override recovery gate failed: empty override data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    open_counts = [_to_int(row.get(args.open_field, ""), csv_path, args.open_field) for row in ordered]
    recoveries = [_to_float(row.get(args.recovery_field, ""), csv_path, args.recovery_field) for row in ordered]

    max_open = max(open_counts)
    report_open = int(report.get("override_open_count", 0))
    if max_open < report_open:
        max_open = report_open

    max_recovery = max(recoveries, default=0.0)
    report_recovery = float(report.get("override_recovery_time_max", 0.0))
    if max_recovery < report_recovery:
        max_recovery = report_recovery

    if max_open > args.max_open_overrides:
        fail(f"D109 max_open_overrides={max_open} > max_open_overrides={args.max_open_overrides}")
    if max_recovery > args.max_recovery_time:
        fail(f"D109 max_recovery_time={max_recovery} > max_recovery_time={args.max_recovery_time}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D113 override pressure gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D113 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D113 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D113 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D113 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D113 invalid override CSV {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        fail(f"D113 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--open-field", default="open_overrides")
    parser.add_argument("--stalled-field", default="stalled_overrides")
    parser.add_argument("--max-open-overrides", type=int, default=0)
    parser.add_argument("--max-stalled-overrides", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.open_field, args.stalled_field})
    if not rows:
        fail("D113 override pressure gate failed: empty override data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    open_counts = [_to_int(row[args.open_field], csv_path, args.open_field) for row in ordered]
    stalled_counts = [_to_int(row[args.stalled_field], csv_path, args.stalled_field) for row in ordered]

    max_open = max(open_counts)
    max_stalled = max(stalled_counts)

    report_open = int(report.get("override_open_count", 0))
    report_stalled = int(report.get("override_stalled_count", 0))
    if max_open < report_open:
        max_open = report_open
    if max_stalled < report_stalled:
        max_stalled = report_stalled

    if max_open > args.max_open_overrides:
        fail(f"D113 max_open_overrides={max_open} > max_open_overrides={args.max_open_overrides}")
    if max_stalled > args.max_stalled_overrides:
        fail(
            f"D113 max_stalled_overrides={max_stalled} > "
            f"max_stalled_overrides={args.max_stalled_overrides}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

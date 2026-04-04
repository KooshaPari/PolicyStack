#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E117 override pressure trend gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E117 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E117 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E117 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E117 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E117 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E117 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E117 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E117 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--open-field", default="open_overrides")
    parser.add_argument("--stalled-field", default="stalled_overrides")
    parser.add_argument("--max-open-overrides", type=int, default=0)
    parser.add_argument("--max-stalled-overrides", type=int, default=0)
    parser.add_argument("--max-pressure-rise", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    overrides_path = pathlib.Path(args.overrides)
    _require_file(report_path, "report")
    _require_file(overrides_path, "overrides")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        overrides_path,
        {args.time_field, args.open_field, args.stalled_field},
        "overrides",
    )
    if not rows:
        fail("E117 empty override data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    open_counts = [_to_int(row[args.open_field], overrides_path, args.open_field) for row in ordered]
    stalled_counts = [_to_int(row[args.stalled_field], overrides_path, args.stalled_field) for row in ordered]
    pressures = [open_v + stalled_v for open_v, stalled_v in zip(open_counts, stalled_counts)]
    rises = [max(0, curr - prev) for prev, curr in zip(pressures, pressures[1:])]
    max_rise = max(rises) if rises else 0

    max_open = max(open_counts)
    max_stalled = max(stalled_counts)
    report_open = _to_int(report.get("override_open_count", 0), report_path, "override_open_count")
    report_stalled = _to_int(
        report.get("override_stalled_count", 0), report_path, "override_stalled_count"
    )
    report_rise = _to_int(
        report.get("override_pressure_trend_rise_max", 0), report_path, "override_pressure_trend_rise_max"
    )

    if max_open < report_open:
        max_open = report_open
    if max_stalled < report_stalled:
        max_stalled = report_stalled
    if max_rise < report_rise:
        max_rise = report_rise

    if max_open > args.max_open_overrides:
        fail(f"E117 max_open_overrides={max_open} > max_open_overrides={args.max_open_overrides}")
    if max_stalled > args.max_stalled_overrides:
        fail(
            f"E117 max_stalled_overrides={max_stalled} > "
            f"max_stalled_overrides={args.max_stalled_overrides}"
        )
    if max_rise > args.max_pressure_rise:
        fail(f"E117 max_pressure_rise={max_rise} > max_pressure_rise={args.max_pressure_rise}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

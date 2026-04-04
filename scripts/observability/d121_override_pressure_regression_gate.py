#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E121 override pressure regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E121 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E121 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E121 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E121 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E121 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E121 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E121 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E121 invalid {field} in {path}: {exc}")


def _max_positive_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max((max(0.0, curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--pressure-field", default="override_pressure")
    parser.add_argument("--regression-field", default="regression_score")
    parser.add_argument("--max-pressure", type=float, default=0.0)
    parser.add_argument("--max-regression", type=float, default=0.0)
    parser.add_argument("--max-pressure-rise", type=float, default=0.0)
    parser.add_argument("--max-regression-rise", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    overrides_path = pathlib.Path(args.overrides)
    _require_file(report_path, "report")
    _require_file(overrides_path, "overrides")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        overrides_path,
        {args.time_field, args.pressure_field, args.regression_field},
        "overrides",
    )
    if not rows:
        fail("E121 empty override data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    pressures = [_to_float(row[args.pressure_field], overrides_path, args.pressure_field) for row in ordered]
    regressions = [
        _to_float(row[args.regression_field], overrides_path, args.regression_field)
        for row in ordered
    ]

    max_pressure = max(pressures)
    max_regression = max(regressions)
    max_pressure_rise = _max_positive_step(pressures)
    max_regression_rise = _max_positive_step(regressions)

    report_pressure = _to_float(
        report.get("override_pressure_max", 0.0),
        report_path,
        "override_pressure_max",
    )
    report_regression = _to_float(
        report.get("override_regression_max", 0.0),
        report_path,
        "override_regression_max",
    )
    report_pressure_rise = _to_float(
        report.get("override_pressure_rise_max", 0.0),
        report_path,
        "override_pressure_rise_max",
    )
    report_regression_rise = _to_float(
        report.get("override_regression_rise_max", 0.0),
        report_path,
        "override_regression_rise_max",
    )

    if max_pressure < report_pressure:
        max_pressure = report_pressure
    if max_regression < report_regression:
        max_regression = report_regression
    if max_pressure_rise < report_pressure_rise:
        max_pressure_rise = report_pressure_rise
    if max_regression_rise < report_regression_rise:
        max_regression_rise = report_regression_rise

    if max_pressure > args.max_pressure:
        fail(f"E121 max_pressure={max_pressure} > max_pressure={args.max_pressure}")
    if max_regression > args.max_regression:
        fail(f"E121 max_regression={max_regression} > max_regression={args.max_regression}")
    if max_pressure_rise > args.max_pressure_rise:
        fail(f"E121 max_pressure_rise={max_pressure_rise} > max_pressure_rise={args.max_pressure_rise}")
    if max_regression_rise > args.max_regression_rise:
        fail(
            f"E121 max_regression_rise={max_regression_rise} > "
            f"max_regression_rise={args.max_regression_rise}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

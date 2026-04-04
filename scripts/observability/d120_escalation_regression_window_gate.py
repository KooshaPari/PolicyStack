#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E120 escalation regression window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E120 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E120 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E120 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E120 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E120 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E120 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E120 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E120 invalid {field} in {path}: {exc}")


def _window_max_average(values: list[float], window_size: int) -> float:
    if not values:
        return 0.0
    if window_size <= 0:
        return max(values)
    if len(values) < window_size:
        return sum(values) / len(values)
    best = float("-inf")
    running = sum(values[:window_size])
    best = running / window_size
    for idx in range(window_size, len(values)):
        running += values[idx] - values[idx - window_size]
        avg = running / window_size
        if avg > best:
            best = avg
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--rate-field", default="escalation_rate")
    parser.add_argument("--regression-field", default="regression_score")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-escalation-rate", type=float, default=0.0)
    parser.add_argument("--max-window-regression-score", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    escalations_path = pathlib.Path(args.escalations)
    _require_file(report_path, "report")
    _require_file(escalations_path, "escalations")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        escalations_path,
        {args.time_field, args.rate_field, args.regression_field},
        "escalations",
    )
    if not rows:
        fail("E120 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    rates = [_to_float(row[args.rate_field], escalations_path, args.rate_field) for row in ordered]
    regressions = [
        _to_float(row[args.regression_field], escalations_path, args.regression_field)
        for row in ordered
    ]

    window_rate = _window_max_average(rates, args.window_size)
    window_regression = _window_max_average(regressions, args.window_size)

    report_rate = _to_float(
        report.get("escalation_window_rate_max", 0.0), report_path, "escalation_window_rate_max"
    )
    report_regression = _to_float(
        report.get("escalation_window_regression_max", 0.0),
        report_path,
        "escalation_window_regression_max",
    )

    if window_rate < report_rate:
        window_rate = report_rate
    if window_regression < report_regression:
        window_regression = report_regression

    if window_rate > args.max_window_escalation_rate:
        fail(
            f"E120 window_escalation_rate={window_rate} > "
            f"max_window_escalation_rate={args.max_window_escalation_rate}"
        )
    if window_regression > args.max_window_regression_score:
        fail(
            f"E120 window_regression_score={window_regression} > "
            f"max_window_regression_score={args.max_window_regression_score}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

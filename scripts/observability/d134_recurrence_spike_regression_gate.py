#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E134 recurrence spike regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E134 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E134 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E134 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E134 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E134 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E134 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E134 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E134 invalid {field} in {path}: {exc}")


def _max_positive_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max((max(0.0, curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--rate-field", default="recurrence_rate")
    parser.add_argument("--regression-field", default="regression_score")
    parser.add_argument("--spike-threshold", type=float, default=0.0)
    parser.add_argument("--max-spike-count", type=int, default=0)
    parser.add_argument("--max-spike-rate", type=float, default=0.0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-regression-score", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    recurrence_path = pathlib.Path(args.recurrence)
    _require_file(report_path, "report")
    _require_file(recurrence_path, "recurrence")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        recurrence_path,
        {args.time_field, args.rate_field, args.regression_field},
        "recurrence",
    )
    if not rows:
        fail("E134 empty recurrence data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    rates = [_to_float(row[args.rate_field], recurrence_path, args.rate_field) for row in ordered]
    regressions = [
        _to_float(row[args.regression_field], recurrence_path, args.regression_field)
        for row in ordered
    ]

    deltas = [max(0.0, curr - prev) for prev, curr in zip(rates, rates[1:])]
    spike_count = sum(1 for delta in deltas if delta > args.spike_threshold)
    spike_rate = max(deltas) if deltas else 0.0
    regression_rate = _max_positive_step(regressions)
    regression_score = max(regressions) if regressions else 0.0

    report_spike_count = int(
        round(
            _to_float(
                report.get("recurrence_spike_count_max", 0),
                report_path,
                "recurrence_spike_count_max",
            )
        )
    )
    report_spike_rate = _to_float(
        report.get("recurrence_spike_rate_max", 0.0),
        report_path,
        "recurrence_spike_rate_max",
    )
    report_regression_rate = _to_float(
        report.get("recurrence_regression_rate_max", 0.0),
        report_path,
        "recurrence_regression_rate_max",
    )
    report_regression_score = _to_float(
        report.get("recurrence_regression_score_max", 0.0),
        report_path,
        "recurrence_regression_score_max",
    )

    if spike_count < report_spike_count:
        spike_count = report_spike_count
    if spike_rate < report_spike_rate:
        spike_rate = report_spike_rate
    if regression_rate < report_regression_rate:
        regression_rate = report_regression_rate
    if regression_score < report_regression_score:
        regression_score = report_regression_score

    if spike_count > args.max_spike_count:
        fail(f"E134 spike_count={spike_count} > max_spike_count={args.max_spike_count}")
    if spike_rate > args.max_spike_rate:
        fail(f"E134 spike_rate={spike_rate} > max_spike_rate={args.max_spike_rate}")
    if regression_rate > args.max_regression_rate:
        fail(
            f"E134 regression_rate={regression_rate} > "
            f"max_regression_rate={args.max_regression_rate}"
        )
    if regression_score > args.max_regression_score:
        fail(
            f"E134 regression_score={regression_score} > "
            f"max_regression_score={args.max_regression_score}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

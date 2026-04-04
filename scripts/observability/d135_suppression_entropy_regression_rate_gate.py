#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E135 suppression entropy regression rate gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E135 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E135 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E135 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E135 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E135 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E135 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E135 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E135 invalid {field} in {path}: {exc}")


def _max_abs_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max((abs(curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)


def _max_positive_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max((max(0.0, curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--entropy-field", default="entropy")
    parser.add_argument("--regression-rate-field", default="regression_rate")
    parser.add_argument("--max-entropy-span", type=float, default=0.0)
    parser.add_argument("--max-entropy-step", type=float, default=0.0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-regression-rate-step", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    suppression_path = pathlib.Path(args.suppression)
    _require_file(report_path, "report")
    _require_file(suppression_path, "suppression")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        suppression_path,
        {args.time_field, args.entropy_field, args.regression_rate_field},
        "suppression",
    )
    if not rows:
        fail("E135 empty suppression data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    entropies = [_to_float(row[args.entropy_field], suppression_path, args.entropy_field) for row in ordered]
    regression_rates = [
        _to_float(row[args.regression_rate_field], suppression_path, args.regression_rate_field)
        for row in ordered
    ]

    entropy_span = max(entropies) - min(entropies)
    entropy_step = _max_abs_step(entropies)
    regression_rate = max(regression_rates) if regression_rates else 0.0
    regression_rate_step = _max_positive_step(regression_rates)

    report_entropy_span = _to_float(
        report.get("suppression_entropy_span_max", 0.0),
        report_path,
        "suppression_entropy_span_max",
    )
    report_entropy_step = _to_float(
        report.get("suppression_entropy_step_max", 0.0),
        report_path,
        "suppression_entropy_step_max",
    )
    report_regression_rate = _to_float(
        report.get("suppression_regression_rate_max", 0.0),
        report_path,
        "suppression_regression_rate_max",
    )
    report_regression_rate_step = _to_float(
        report.get("suppression_regression_rate_step_max", 0.0),
        report_path,
        "suppression_regression_rate_step_max",
    )

    if entropy_span < report_entropy_span:
        entropy_span = report_entropy_span
    if entropy_step < report_entropy_step:
        entropy_step = report_entropy_step
    if regression_rate < report_regression_rate:
        regression_rate = report_regression_rate
    if regression_rate_step < report_regression_rate_step:
        regression_rate_step = report_regression_rate_step

    if entropy_span > args.max_entropy_span:
        fail(f"E135 entropy_span={entropy_span} > max_entropy_span={args.max_entropy_span}")
    if entropy_step > args.max_entropy_step:
        fail(f"E135 entropy_step={entropy_step} > max_entropy_step={args.max_entropy_step}")
    if regression_rate > args.max_regression_rate:
        fail(
            f"E135 regression_rate={regression_rate} > "
            f"max_regression_rate={args.max_regression_rate}"
        )
    if regression_rate_step > args.max_regression_rate_step:
        fail(
            f"E135 regression_rate_step={regression_rate_step} > "
            f"max_regression_rate_step={args.max_regression_rate_step}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E123 suppression entropy regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E123 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E123 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E123 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E123 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E123 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E123 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E123 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E123 invalid {field} in {path}: {exc}")


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
    parser.add_argument("--regression-field", default="regression_score")
    parser.add_argument("--max-entropy", type=float, default=0.0)
    parser.add_argument("--max-regression", type=float, default=0.0)
    parser.add_argument("--max-entropy-rise", type=float, default=0.0)
    parser.add_argument("--max-regression-rise", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    suppression_path = pathlib.Path(args.suppression)
    _require_file(report_path, "report")
    _require_file(suppression_path, "suppression")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        suppression_path,
        {args.time_field, args.entropy_field, args.regression_field},
        "suppression",
    )
    if not rows:
        fail("E123 empty suppression data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    entropies = [_to_float(row[args.entropy_field], suppression_path, args.entropy_field) for row in ordered]
    regressions = [
        _to_float(row[args.regression_field], suppression_path, args.regression_field)
        for row in ordered
    ]

    max_entropy = max(entropies)
    max_regression = max(regressions)
    max_entropy_rise = _max_positive_step(entropies)
    max_regression_rise = _max_positive_step(regressions)

    report_entropy = _to_float(
        report.get("suppression_entropy_max", 0.0),
        report_path,
        "suppression_entropy_max",
    )
    report_regression = _to_float(
        report.get("suppression_regression_max", 0.0),
        report_path,
        "suppression_regression_max",
    )
    report_entropy_rise = _to_float(
        report.get("suppression_entropy_rise_max", 0.0),
        report_path,
        "suppression_entropy_rise_max",
    )
    report_regression_rise = _to_float(
        report.get("suppression_regression_rise_max", 0.0),
        report_path,
        "suppression_regression_rise_max",
    )

    if max_entropy < report_entropy:
        max_entropy = report_entropy
    if max_regression < report_regression:
        max_regression = report_regression
    if max_entropy_rise < report_entropy_rise:
        max_entropy_rise = report_entropy_rise
    if max_regression_rise < report_regression_rise:
        max_regression_rise = report_regression_rise

    if max_entropy > args.max_entropy:
        fail(f"E123 max_entropy={max_entropy} > max_entropy={args.max_entropy}")
    if max_regression > args.max_regression:
        fail(f"E123 max_regression={max_regression} > max_regression={args.max_regression}")
    if max_entropy_rise > args.max_entropy_rise:
        fail(f"E123 max_entropy_rise={max_entropy_rise} > max_entropy_rise={args.max_entropy_rise}")
    if max_regression_rise > args.max_regression_rise:
        fail(
            f"E123 max_regression_rise={max_regression_rise} > "
            f"max_regression_rise={args.max_regression_rise}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

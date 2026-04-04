#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E143 suppression entropy window regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E143 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E143 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E143 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E143 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E143 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E143 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E143 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E143 invalid {field} in {path}: {exc}")


def _window_pairs(values: list[float], window_size: int) -> list[list[float]]:
    if not values:
        return []
    if window_size <= 0 or window_size > len(values):
        return [values]
    return [values[start : start + window_size] for start in range(0, len(values) - window_size + 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--entropy-field", default="entropy")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-regression", type=float, default=0.0)
    parser.add_argument("--max-window-regression-mean", type=float, default=0.0)
    parser.add_argument("--max-window-regression-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    suppression_path = pathlib.Path(args.suppression)
    _require_file(report_path, "report")
    _require_file(suppression_path, "suppression")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        suppression_path,
        {args.time_field, args.entropy_field},
        "suppression",
    )
    if not rows:
        fail("E143 empty suppression data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    entropy = [_to_float(row[args.entropy_field], suppression_path, args.entropy_field) for row in ordered]
    regressions = [max(0.0, curr - prev) for prev, curr in zip(entropy, entropy[1:])]

    window_values = _window_pairs(regressions, args.window_size)
    window_regression = max((max(window) for window in window_values), default=0.0)
    window_regression_mean = max(
        ((sum(window) / float(len(window))) for window in window_values),
        default=0.0,
    )
    window_regression_count = max(
        (sum(1 for value in window if value > 0.0) for window in window_values),
        default=0,
    )

    report_window_regression = _to_float(
        report.get("suppression_entropy_window_regression_max", 0.0),
        report_path,
        "suppression_entropy_window_regression_max",
    )
    report_window_regression_mean = _to_float(
        report.get("suppression_entropy_window_regression_mean", 0.0),
        report_path,
        "suppression_entropy_window_regression_mean",
    )
    report_window_regression_count = int(
        round(
            _to_float(
                report.get("suppression_entropy_window_regression_count_max", 0),
                report_path,
                "suppression_entropy_window_regression_count_max",
            )
        )
    )

    if window_regression < report_window_regression:
        window_regression = report_window_regression
    if window_regression_mean < report_window_regression_mean:
        window_regression_mean = report_window_regression_mean
    if window_regression_count < report_window_regression_count:
        window_regression_count = report_window_regression_count

    if window_regression > args.max_window_regression:
        fail(
            f"E143 window_regression={window_regression} > "
            f"max_window_regression={args.max_window_regression}"
        )
    if window_regression_mean > args.max_window_regression_mean:
        fail(
            f"E143 window_regression_mean={window_regression_mean} > "
            f"max_window_regression_mean={args.max_window_regression_mean}"
        )
    if window_regression_count > args.max_window_regression_count:
        fail(
            f"E143 window_regression_count={window_regression_count} > "
            f"max_window_regression_count={args.max_window_regression_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

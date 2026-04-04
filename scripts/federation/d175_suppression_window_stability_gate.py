#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E175 suppression entropy window budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E175 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E175 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E175 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E175 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E175 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E175 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E175 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E175 invalid {field} in {path}: {exc}")


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
    parser.add_argument("--budget-field", default="entropy_budget")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-budget-gap", type=float, default=0.0)
    parser.add_argument("--max-window-budget-gap-mean", type=float, default=0.0)
    parser.add_argument("--max-window-over-budget-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    suppression_path = pathlib.Path(args.suppression)
    _require_file(report_path, "report")
    _require_file(suppression_path, "suppression")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        suppression_path,
        {args.time_field, args.entropy_field, args.budget_field},
        "suppression",
    )
    if not rows:
        fail("E175 empty suppression data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    gaps: list[float] = []
    for row in ordered:
        entropy = _to_float(row[args.entropy_field], suppression_path, args.entropy_field)
        budget = _to_float(row[args.budget_field], suppression_path, args.budget_field)
        gaps.append(max(0.0, entropy - budget))

    window_values = _window_pairs(gaps, args.window_size)
    window_budget_gap = max((max(window) for window in window_values), default=0.0)
    window_budget_gap_mean = max(
        ((sum(window) / float(len(window))) for window in window_values),
        default=0.0,
    )
    window_over_budget_count = max(
        (sum(1 for value in window if value > 0.0) for window in window_values),
        default=0,
    )

    report_window_budget_gap = _to_float(
        report.get("suppression_entropy_window_budget_gap_max", 0.0),
        report_path,
        "suppression_entropy_window_budget_gap_max",
    )
    report_window_budget_gap_mean = _to_float(
        report.get("suppression_entropy_window_budget_gap_mean", 0.0),
        report_path,
        "suppression_entropy_window_budget_gap_mean",
    )
    report_window_over_budget_count = int(
        round(
            _to_float(
                report.get("suppression_entropy_window_budget_over_budget_count_max", 0),
                report_path,
                "suppression_entropy_window_budget_over_budget_count_max",
            )
        )
    )

    if window_budget_gap < report_window_budget_gap:
        window_budget_gap = report_window_budget_gap
    if window_budget_gap_mean < report_window_budget_gap_mean:
        window_budget_gap_mean = report_window_budget_gap_mean
    if window_over_budget_count < report_window_over_budget_count:
        window_over_budget_count = report_window_over_budget_count

    if window_budget_gap > args.max_window_budget_gap:
        fail(
            f"E175 window_budget_gap={window_budget_gap} > "
            f"max_window_budget_gap={args.max_window_budget_gap}"
        )
    if window_budget_gap_mean > args.max_window_budget_gap_mean:
        fail(
            f"E175 window_budget_gap_mean={window_budget_gap_mean} > "
            f"max_window_budget_gap_mean={args.max_window_budget_gap_mean}"
        )
    if window_over_budget_count > args.max_window_over_budget_count:
        fail(
            f"E175 window_over_budget_count={window_over_budget_count} > "
            f"max_window_over_budget_count={args.max_window_over_budget_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

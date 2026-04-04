#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E218 recurrence regression budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E218 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E218 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E218 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E218 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E218 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E218 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E218 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E218 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--regression-field", default="regression_score")
    parser.add_argument("--budget-field", default="regression_budget")
    parser.add_argument("--max-regression-budget-gap", type=float, default=0.0)
    parser.add_argument("--max-regression-budget-gap-mean", type=float, default=0.0)
    parser.add_argument("--max-over-budget-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    recurrence_path = pathlib.Path(args.recurrence)
    _require_file(report_path, "report")
    _require_file(recurrence_path, "recurrence")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        recurrence_path,
        {args.time_field, args.regression_field, args.budget_field},
        "recurrence",
    )
    if not rows:
        fail("E218 empty recurrence data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    gaps: list[float] = []
    for row in ordered:
        regression = _to_float(row[args.regression_field], recurrence_path, args.regression_field)
        budget = _to_float(row[args.budget_field], recurrence_path, args.budget_field)
        gaps.append(max(0.0, regression - budget))

    regression_budget_gap = max(gaps) if gaps else 0.0
    regression_budget_gap_mean = (sum(gaps) / float(len(gaps))) if gaps else 0.0
    over_budget_count = sum(1 for value in gaps if value > 0.0)

    report_regression_budget_gap = _to_float(
        report.get("recurrence_regression_budget_gap_max", 0.0),
        report_path,
        "recurrence_regression_budget_gap_max",
    )
    report_regression_budget_gap_mean = _to_float(
        report.get("recurrence_regression_budget_gap_mean", 0.0),
        report_path,
        "recurrence_regression_budget_gap_mean",
    )
    report_over_budget_count = int(
        round(
            _to_float(
                report.get("recurrence_regression_over_budget_count", 0),
                report_path,
                "recurrence_regression_over_budget_count",
            )
        )
    )

    if regression_budget_gap < report_regression_budget_gap:
        regression_budget_gap = report_regression_budget_gap
    if regression_budget_gap_mean < report_regression_budget_gap_mean:
        regression_budget_gap_mean = report_regression_budget_gap_mean
    if over_budget_count < report_over_budget_count:
        over_budget_count = report_over_budget_count

    if regression_budget_gap > args.max_regression_budget_gap:
        fail(
            f"E218 regression_budget_gap={regression_budget_gap} > "
            f"max_regression_budget_gap={args.max_regression_budget_gap}"
        )
    if regression_budget_gap_mean > args.max_regression_budget_gap_mean:
        fail(
            f"E218 regression_budget_gap_mean={regression_budget_gap_mean} > "
            f"max_regression_budget_gap_mean={args.max_regression_budget_gap_mean}"
        )
    if over_budget_count > args.max_over_budget_count:
        fail(
            f"E218 over_budget_count={over_budget_count} > "
            f"max_over_budget_count={args.max_over_budget_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E119 suppression entropy budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E119 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E119 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E119 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E119 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E119 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E119 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E119 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E119 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--entropy-field", default="entropy")
    parser.add_argument("--max-entropy", type=float, default=0.0)
    parser.add_argument("--max-entropy-step-rate", type=float, default=0.0)
    parser.add_argument("--max-budget-breach-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    suppression_path = pathlib.Path(args.suppression)
    _require_file(report_path, "report")
    _require_file(suppression_path, "suppression")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(suppression_path, {args.time_field, args.entropy_field}, "suppression")
    if not rows:
        fail("E119 empty suppression data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time-field, "")))
    entropies = [_to_float(row[args.entropy_field], suppression_path, args.entropy_field) for row in ordered]
    max_entropy = max(entropies)
    step_rate = max((abs(curr - prev) for prev, curr in zip(entropies, entropies[1:])), default=0.0)
    breach_count = sum(1 for value in entropies if value > args.max_entropy)

    report_entropy = _to_float(report.get("suppression_entropy_max", 0.0), report_path, "suppression_entropy_max")
    report_step = _to_float(
        report.get("suppression_entropy_step_rate_max", 0.0), report_path, "suppression_entropy_step_rate_max"
    )
    report_breach = int(round(_to_float(
        report.get("suppression_entropy_budget_breach_count", 0),
        report_path,
        "suppression_entropy_budget_breach_count",
    )))

    if max_entropy < report_entropy:
        max_entropy = report_entropy
    if step_rate < report_step:
        step_rate = report_step
    if breach_count < report_breach:
        breach_count = report_breach

    if max_entropy > args.max_entropy:
        fail(f"E119 max_entropy={max_entropy} > max_entropy={args.max_entropy}")
    if step_rate > args.max_entropy_step_rate:
        fail(
            f"E119 max_entropy_step_rate={step_rate} > "
            f"max_entropy_step_rate={args.max_entropy_step_rate}"
        )
    if breach_count > args.max_budget_breach_count:
        fail(
            f"E119 budget_breach_count={breach_count} > "
            f"max_budget_breach_count={args.max_budget_breach_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

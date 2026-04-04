#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E152 escalation recovery entropy budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E152 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E152 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E152 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E152 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E152 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E152 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E152 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E152 invalid {field} in {path}: {exc}")


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E152 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--open-field", default="open_escalations")
    parser.add_argument("--recovered-field", default="recovered_escalations")
    parser.add_argument("--entropy-field", default="recovery_entropy")
    parser.add_argument("--entropy-budget-field", default="recovery_entropy_budget")
    parser.add_argument("--max-entropy-budget-gap", type=float, default=0.0)
    parser.add_argument("--max-entropy-budget-gap-mean", type=float, default=0.0)
    parser.add_argument("--max-over-budget-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    escalations_path = pathlib.Path(args.escalations)
    _require_file(report_path, "report")
    _require_file(escalations_path, "escalations")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        escalations_path,
        {
            args.time_field,
            args.open_field,
            args.recovered_field,
            args.entropy_field,
            args.entropy_budget_field,
        },
        "escalations",
    )
    if not rows:
        fail("E152 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    open_counts = [_to_int(row[args.open_field], escalations_path, args.open_field) for row in ordered]
    recovered_counts = [
        _to_int(row[args.recovered_field], escalations_path, args.recovered_field)
        for row in ordered
    ]
    entropies = [
        _to_float(row[args.entropy_field], escalations_path, args.entropy_field)
        for row in ordered
    ]
    budgets = [
        _to_float(row[args.entropy_budget_field], escalations_path, args.entropy_budget_field)
        for row in ordered
    ]

    entropy_gaps: list[float] = []
    for open_count, recovered_count, entropy, budget in zip(
        open_counts, recovered_counts, entropies, budgets
    ):
        if open_count <= 0:
            unrecovered_ratio = 0.0
        else:
            recovered_ratio = min(1.0, max(0.0, float(recovered_count) / float(open_count)))
            unrecovered_ratio = 1.0 - recovered_ratio
        entropy_pressure = unrecovered_ratio * max(0.0, entropy)
        entropy_gaps.append(max(0.0, entropy_pressure - budget))

    entropy_budget_gap = max(entropy_gaps) if entropy_gaps else 0.0
    entropy_budget_gap_mean = (
        (sum(entropy_gaps) / float(len(entropy_gaps))) if entropy_gaps else 0.0
    )
    over_budget_count = sum(1 for value in entropy_gaps if value > 0.0)

    report_entropy_budget_gap = _to_float(
        report.get("escalation_recovery_entropy_budget_gap_max", 0.0),
        report_path,
        "escalation_recovery_entropy_budget_gap_max",
    )
    report_entropy_budget_gap_mean = _to_float(
        report.get("escalation_recovery_entropy_budget_gap_mean", 0.0),
        report_path,
        "escalation_recovery_entropy_budget_gap_mean",
    )
    report_over_budget_count = int(
        round(
            _to_float(
                report.get("escalation_recovery_entropy_over_budget_count", 0),
                report_path,
                "escalation_recovery_entropy_over_budget_count",
            )
        )
    )

    if entropy_budget_gap < report_entropy_budget_gap:
        entropy_budget_gap = report_entropy_budget_gap
    if entropy_budget_gap_mean < report_entropy_budget_gap_mean:
        entropy_budget_gap_mean = report_entropy_budget_gap_mean
    if over_budget_count < report_over_budget_count:
        over_budget_count = report_over_budget_count

    if entropy_budget_gap > args.max_entropy_budget_gap:
        fail(
            f"E152 entropy_budget_gap={entropy_budget_gap} > "
            f"max_entropy_budget_gap={args.max_entropy_budget_gap}"
        )
    if entropy_budget_gap_mean > args.max_entropy_budget_gap_mean:
        fail(
            f"E152 entropy_budget_gap_mean={entropy_budget_gap_mean} > "
            f"max_entropy_budget_gap_mean={args.max_entropy_budget_gap_mean}"
        )
    if over_budget_count > args.max_over_budget_count:
        fail(
            f"E152 over_budget_count={over_budget_count} > "
            f"max_over_budget_count={args.max_over_budget_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

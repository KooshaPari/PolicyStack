#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E248 escalation recovery window budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E248 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E248 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E248 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E248 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E248 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E248 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E248 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E248 invalid {field} in {path}: {exc}")


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E248 invalid {field} in {path}: {exc}")


def _window_pairs(values: list[float], window_size: int) -> list[list[float]]:
    if not values:
        return []
    if window_size <= 0 or window_size > len(values):
        return [values]
    return [values[start : start + window_size] for start in range(0, len(values) - window_size + 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--open-field", default="open_escalations")
    parser.add_argument("--recovered-field", default="recovered_escalations")
    parser.add_argument("--recovery-window-field", default="recovery_window_hours")
    parser.add_argument("--budget-field", default="recovery_budget")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-budget-gap", type=float, default=0.0)
    parser.add_argument("--max-window-budget-gap-mean", type=float, default=0.0)
    parser.add_argument("--max-window-over-budget-count", type=int, default=0)
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
            args.recovery_window_field,
            args.budget_field,
        },
        "escalations",
    )
    if not rows:
        fail("E248 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    gaps: list[float] = []
    for row in ordered:
        open_count = _to_int(row[args.open_field], escalations_path, args.open_field)
        recovered_count = _to_int(row[args.recovered_field], escalations_path, args.recovered_field)
        recovery_window = _to_float(
            row[args.recovery_window_field],
            escalations_path,
            args.recovery_window_field,
        )
        budget = _to_float(row[args.budget_field], escalations_path, args.budget_field)

        if open_count <= 0:
            unrecovered_ratio = 0.0
        else:
            recovered_ratio = min(1.0, max(0.0, float(recovered_count) / float(open_count)))
            unrecovered_ratio = 1.0 - recovered_ratio

        recovery_pressure = unrecovered_ratio * max(0.0, recovery_window)
        gaps.append(max(0.0, recovery_pressure - budget))

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
        report.get("escalation_recovery_window_budget_gap_max", 0.0),
        report_path,
        "escalation_recovery_window_budget_gap_max",
    )
    report_window_budget_gap_mean = _to_float(
        report.get("escalation_recovery_window_budget_gap_mean", 0.0),
        report_path,
        "escalation_recovery_window_budget_gap_mean",
    )
    report_window_over_budget_count = int(
        round(
            _to_float(
                report.get("escalation_recovery_window_budget_over_budget_count_max", 0),
                report_path,
                "escalation_recovery_window_budget_over_budget_count_max",
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
            f"E248 window_budget_gap={window_budget_gap} > "
            f"max_window_budget_gap={args.max_window_budget_gap}"
        )
    if window_budget_gap_mean > args.max_window_budget_gap_mean:
        fail(
            f"E248 window_budget_gap_mean={window_budget_gap_mean} > "
            f"max_window_budget_gap_mean={args.max_window_budget_gap_mean}"
        )
    if window_over_budget_count > args.max_window_over_budget_count:
        fail(
            f"E248 window_over_budget_count={window_over_budget_count} > "
            f"max_window_over_budget_count={args.max_window_over_budget_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

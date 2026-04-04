#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E138 recurrence spike budget window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E138 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E138 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E138 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E138 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E138 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E138 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E138 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E138 invalid {field} in {path}: {exc}")


def _window_pairs(values: list[float], window_size: int) -> list[list[float]]:
    if not values:
        return []
    if window_size <= 0 or window_size > len(values):
        return [values]
    return [values[start : start + window_size] for start in range(0, len(values) - window_size + 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--rate-field", default="recurrence_rate")
    parser.add_argument("--spike-threshold", type=float, default=0.0)
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-spike-count", type=int, default=0)
    parser.add_argument("--max-window-spike-rate", type=float, default=0.0)
    parser.add_argument("--max-window-spike-budget-gap", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    recurrence_path = pathlib.Path(args.recurrence)
    _require_file(report_path, "report")
    _require_file(recurrence_path, "recurrence")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        recurrence_path,
        {args.time_field, args.rate_field},
        "recurrence",
    )
    if not rows:
        fail("E138 empty recurrence data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    rates = [_to_float(row[args.rate_field], recurrence_path, args.rate_field) for row in ordered]
    spikes = [max(0.0, curr - prev) for prev, curr in zip(rates, rates[1:])]

    spike_window_values = _window_pairs(spikes, args.window_size)
    window_spike_count = max(
        (sum(1 for spike in window if spike > args.spike_threshold) for window in spike_window_values),
        default=0,
    )
    window_spike_rate = max((max(window) for window in spike_window_values), default=0.0)
    window_spike_budget_gap = max(
        (sum(max(0.0, spike - args.spike_threshold) for spike in window) for window in spike_window_values),
        default=0.0,
    )

    report_window_spike_count = int(
        round(
            _to_float(
                report.get("recurrence_spike_window_count_max", 0),
                report_path,
                "recurrence_spike_window_count_max",
            )
        )
    )
    report_window_spike_rate = _to_float(
        report.get("recurrence_spike_window_rate_max", 0.0),
        report_path,
        "recurrence_spike_window_rate_max",
    )
    report_window_spike_budget_gap = _to_float(
        report.get("recurrence_spike_budget_window_gap_max", 0.0),
        report_path,
        "recurrence_spike_budget_window_gap_max",
    )

    if window_spike_count < report_window_spike_count:
        window_spike_count = report_window_spike_count
    if window_spike_rate < report_window_spike_rate:
        window_spike_rate = report_window_spike_rate
    if window_spike_budget_gap < report_window_spike_budget_gap:
        window_spike_budget_gap = report_window_spike_budget_gap

    if window_spike_count > args.max_window_spike_count:
        fail(
            f"E138 window_spike_count={window_spike_count} > "
            f"max_window_spike_count={args.max_window_spike_count}"
        )
    if window_spike_rate > args.max_window_spike_rate:
        fail(
            f"E138 window_spike_rate={window_spike_rate} > "
            f"max_window_spike_rate={args.max_window_spike_rate}"
        )
    if window_spike_budget_gap > args.max_window_spike_budget_gap:
        fail(
            f"E138 window_spike_budget_gap={window_spike_budget_gap} > "
            f"max_window_spike_budget_gap={args.max_window_spike_budget_gap}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

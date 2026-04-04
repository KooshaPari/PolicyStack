#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E122 recurrence stability window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E122 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E122 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E122 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E122 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E122 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E122 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E122 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E122 invalid {field} in {path}: {exc}")


def _window_max_span(values: list[float], window_size: int) -> float:
    if not values:
        return 0.0
    if window_size <= 0 or window_size > len(values):
        return max(values) - min(values)
    best = 0.0
    for start in range(0, len(values) - window_size + 1):
        window = values[start : start + window_size]
        span = max(window) - min(window)
        if span > best:
            best = span
    return best


def _window_max_step(values: list[float], window_size: int) -> float:
    if len(values) < 2:
        return 0.0
    if window_size <= 1:
        return max((abs(curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)
    best = 0.0
    for start in range(0, len(values) - window_size + 1):
        window = values[start : start + window_size]
        step = max((abs(curr - prev) for prev, curr in zip(window, window[1:])), default=0.0)
        if step > best:
            best = step
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--stability-field", default="stability_score")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-span", type=float, default=0.0)
    parser.add_argument("--max-window-step", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    recurrence_path = pathlib.Path(args.recurrence)
    _require_file(report_path, "report")
    _require_file(recurrence_path, "recurrence")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        recurrence_path,
        {args.time_field, args.stability_field},
        "recurrence",
    )
    if not rows:
        fail("E122 empty recurrence data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    stabilities = [_to_float(row[args.stability_field], recurrence_path, args.stability_field) for row in ordered]

    window_span = _window_max_span(stabilities, args.window_size)
    window_step = _window_max_step(stabilities, args.window_size)

    report_span = _to_float(
        report.get("recurrence_window_span_max", 0.0),
        report_path,
        "recurrence_window_span_max",
    )
    report_step = _to_float(
        report.get("recurrence_window_step_max", 0.0),
        report_path,
        "recurrence_window_step_max",
    )

    if window_span < report_span:
        window_span = report_span
    if window_step < report_step:
        window_step = report_step

    if window_span > args.max_window_span:
        fail(f"E122 window_span={window_span} > max_window_span={args.max_window_span}")
    if window_step > args.max_window_step:
        fail(f"E122 window_step={window_step} > max_window_step={args.max_window_step}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

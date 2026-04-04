#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D88 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D88 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D88 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D88 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D88 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D88 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--max-plateau-value", type=float, default=0.0)
    parser.add_argument("--max-plateau-runs", type=int, default=0)
    parser.add_argument("--plateau-drift", type=float, default=0.0)
    parser.add_argument("--min-plateau-len", type=int, default=3)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"window_start", "open_recurrence"})
    if not rows:
        _fail("D88 recurrence plateau gate failed: empty recurrence csv")

    ordered = sorted(rows, key=lambda row: (row.get("window_start") or "").strip())
    values = [
        _to_float(row.get("open_recurrence", ""), csv_path, "open_recurrence")
        for row in ordered
    ]

    min_plateau_len = max(args.min_plateau_len, 1)
    max_value = float(report.get("recurrence_plateau_value", 0.0))
    breaches = int(report.get("recurrence_plateau_runs", 0))
    run_len = 1
    run_peak = values[0]
    for previous, current in zip(values, values[1:]):
        if abs(current - previous) <= args.plateau_drift:
            run_len += 1
            run_peak = max(run_peak, current)
        else:
            if run_len >= min_plateau_len:
                max_value = max(max_value, run_peak)
                breaches += 1
            run_len = 1
            run_peak = current
    if run_len >= min_plateau_len:
        max_value = max(max_value, run_peak)
        breaches += 1

    if max_value > args.max_plateau_value:
        _fail(f"D88 recurrence plateau gate failed: max_plateau_value={max_value}")
    if breaches > args.max_plateau_runs:
        _fail(f"D88 recurrence plateau gate failed: plateau_runs={breaches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

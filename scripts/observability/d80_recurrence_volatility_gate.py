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
        _fail(f"D80 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D80 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D80 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D80 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D80 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D80 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--max-volatility", type=float, default=0.0)
    parser.add_argument("--max-volatility-spikes", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"window_start", "open_recurrence"})
    if not rows:
        _fail("D80 recurrence volatility gate failed: no recurrence rows")

    sorted_rows = sorted(rows, key=lambda row: (row.get("window_start") or "").strip())
    values = [_to_float(row.get("open_recurrence"), csv_path, "open_recurrence") for row in sorted_rows]

    max_step = 0.0
    spike_count = 0
    for current, previous in zip(values[1:], values[:-1]):
        delta = abs(current - previous)
        max_step = max(max_step, delta)
        if delta > args.max_volatility:
            spike_count += 1

    report_volatility = float(report.get("recurrence_volatility", 0.0))
    report_spikes = int(report.get("recurrence_volatility_spikes", 0))

    max_step = max(max_step, report_volatility)
    spike_count = max(spike_count, report_spikes)

    if max_step > args.max_volatility:
        _fail(f"D80 recurrence volatility gate failed: max_volatility={max_step}")
    if spike_count > args.max_volatility_spikes:
        _fail(f"D80 recurrence volatility gate failed: volatility_spikes={spike_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

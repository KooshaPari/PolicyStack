#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> "None":
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D72 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D72 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D72 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D72 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D72 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--trend-csv", required=True)
    parser.add_argument("--max-trend-delta", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.trend_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "trend")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"period", "open_recurrence"})
    if not rows:
        _fail("D72 recurrence trend CSV has no rows")

    sorted_rows = sorted(rows, key=lambda row: (row.get("period") or "").strip())
    try:
        first_value = float((sorted_rows[0].get("open_recurrence") or "").strip())
        last_value = float((sorted_rows[-1].get("open_recurrence") or "").strip())
    except ValueError as exc:
        _fail(f"D72 invalid open_recurrence value: {exc}")

    csv_delta = last_value - first_value
    report_delta = float(report.get("recurrence_trend_delta", csv_delta))
    effective_delta = max(csv_delta, report_delta)

    if effective_delta > args.max_trend_delta:
        _fail(
            f"D72 recurrence trend nonworsening gate failed: "
            f"trend_delta={effective_delta}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

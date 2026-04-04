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
        _fail(f"D89 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D89 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D89 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D89 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D89 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D89 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--trend-csv", required=True)
    parser.add_argument("--debt-field", default="override_debt")
    parser.add_argument("--time-field", default="period")
    parser.add_argument("--max-trend-delta", type=float, default=0.0)
    parser.add_argument("--max-trend-worsen-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.trend_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "trend")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {args.time_field, args.debt_field})
    if not rows:
        _fail("D89 override debt trend gate failed: empty trend csv")

    sorted_rows = sorted(rows, key=lambda row: (row.get(args.time_field) or "").strip())
    values = [
        _to_float(row.get(args.debt_field), csv_path, args.debt_field)
        for row in sorted_rows
    ]

    trend_delta = values[-1] - values[0]
    worsen_count = sum(current > previous for previous, current in zip(values, values[1:]))

    effective_delta = max(trend_delta, float(report.get("override_debt_trend_delta", trend_delta)))
    effective_worsen = max(
        worsen_count,
        int(report.get("override_debt_trend_worsen_count", worsen_count)),
    )

    if effective_delta > args.max_trend_delta:
        _fail(f"D89 override debt trend gate failed: trend_delta={effective_delta}")
    if effective_worsen > args.max_trend_worsen_count:
        _fail(f"D89 override debt trend gate failed: worsen_count={effective_worsen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

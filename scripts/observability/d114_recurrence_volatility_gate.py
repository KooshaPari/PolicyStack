#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D114 recurrence volatility gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D114 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D114 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D114 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D114 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D114 invalid recurrence CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D114 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--value-field", default="recurrence_rate")
    parser.add_argument("--max-volatility", type=float, default=0.0)
    parser.add_argument("--min-mean-margin", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field})
    if not rows:
        fail("D114 recurrence volatility gate failed: empty recurrence data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    values = [_to_float(row.get(args.value_field, ""), csv_path, args.value_field) for row in ordered]
    if len(values) < 2:
        fail("D114 recurrence volatility gate failed: insufficient recurrence points")

    deltas = [abs(a - b) for a, b in zip(values, values[1:])]
    max_volatility = max(deltas)
    mean_recurrence = sum(values) / len(values)

    report_volatility = float(report.get("recurrence_rate_volatility_max", 0.0))
    if max_volatility < report_volatility:
        max_volatility = report_volatility
    report_margin = float(report.get("recurrence_rate_margin_min", 0.0))
    if mean_recurrence < report_margin:
        mean_recurrence = report_margin

    if max_volatility > args.max_volatility:
        fail(f"D114 max_volatility={max_volatility} > max_volatility={args.max_volatility}")
    if mean_recurrence < args.min_mean_margin:
        fail(f"D114 mean_recurrence={mean_recurrence} < min_mean_margin={args.min_mean_margin}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

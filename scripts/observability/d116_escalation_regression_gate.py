#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D116 escalation regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D116 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D116 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D116 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D116 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D116 invalid escalation CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D116 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--rate-field", default="escalation_rate")
    parser.add_argument("--regression-field", default="regression_score")
    parser.add_argument("--max-regression-score", type=float, default=0.0)
    parser.add_argument("--max-escalation-rate", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.rate_field, args.regression_field})
    if not rows:
        fail("D116 escalation regression gate failed: empty escalation data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    rates = [_to_float(row.get(args.rate_field, ""), csv_path, args.rate_field) for row in ordered]
    regressions = [_to_float(row.get(args.regression_field, ""), csv_path, args.regression_field) for row in ordered]

    max_rate = max(rates)
    max_regression = max(regressions)
    report_rate = float(report.get("escalation_rate_max", 0.0))
    report_regression = float(report.get("escalation_regression_max", 0.0))
    if max_rate < report_rate:
        max_rate = report_rate
    if max_regression < report_regression:
        max_regression = report_regression

    if max_regression > args.max_regression_score:
        fail(
            f"D116 max_regression_score={max_regression} > "
            f"max_regression_score={args.max_regression_score}"
        )
    if max_rate > args.max_escalation_rate:
        fail(f"D116 max_escalation_rate={max_rate} > max_escalation_rate={args.max_escalation_rate}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

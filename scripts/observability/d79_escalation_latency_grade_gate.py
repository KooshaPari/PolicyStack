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
        _fail(f"D79 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D79 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D79 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D79 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D79 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D79 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--min-latency-grade", type=float, default=0.7)
    parser.add_argument("--max-grade-breaches", type=int, default=0)
    args = parser.parse_args()

    metrics_path = pathlib.Path(args.metrics)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(metrics_path, "metrics")
    _require_file(csv_path, "escalations")

    metrics = _load_json(metrics_path)
    rows = _load_csv(csv_path, {"escalation_id", "status", "latency_grade"})

    report_grade = float(metrics.get("escalation_latency_grade", 1.0))
    breaches = 0
    min_grade = report_grade
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in {"open", "active", "in_progress"}:
            continue
        grade = _to_float(row.get("latency_grade", ""), csv_path, "latency_grade")
        min_grade = min(min_grade, grade)
        if grade < args.min_latency_grade:
            breaches += 1

    breaches = max(breaches, int(metrics.get("escalation_latency_grade_breaches", 0)))
    if min_grade < args.min_latency_grade:
        _fail(f"D79 escalation latency grade gate failed: min_grade={min_grade}")
    if breaches > args.max_grade_breaches:
        _fail(f"D79 escalation latency grade gate failed: breaches={breaches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

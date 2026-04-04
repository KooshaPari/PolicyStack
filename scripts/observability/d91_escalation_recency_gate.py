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
        _fail(f"D91 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D91 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D91 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D91 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D91 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D91 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--max-stale-days", type=int, default=30)
    parser.add_argument("--max-stale-escalations", type=int, default=0)
    parser.add_argument("--max-stale-score", type=float, default=1.0)
    parser.add_argument("--recency-field", default="days_since_open")
    parser.add_argument("--score-field", default="recency_score")
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"escalation_id", "status", args.recency_field, args.score_field})

    max_score = float(report.get("escalation_recency_score", 0.0))
    stale_breaches = int(report.get("stale_escalations", 0))

    for row in sorted(rows, key=lambda row: (row.get("escalation_id") or "")):
        status = (row.get("status") or "").strip().lower()
        if status not in {"open", "active", "in_progress"}:
            continue
        stale_days = _to_float(row.get(args.recency_field), csv_path, args.recency_field)
        score = _to_float(row.get(args.score_field), csv_path, args.score_field)
        max_score = max(max_score, score)
        if stale_days > args.max_stale_days:
            stale_breaches += 1
        if score > args.max_stale_score:
            stale_breaches += 1

    if max_score > args.max_stale_score:
        _fail(f"D91 escalation recency gate failed: max_staleness_score={max_score}")
    if stale_breaches > args.max_stale_escalations:
        _fail(f"D91 escalation recency gate failed: stale_escalations={stale_breaches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

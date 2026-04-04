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
        _fail(f"D78 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D78 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D78 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D78 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D78 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D78 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppressions-csv", required=True)
    parser.add_argument("--max-aging-score", type=float, default=1.0)
    parser.add_argument("--max-aging-suppressions", type=int, default=0)
    parser.add_argument("--max-aging-days", type=int, default=30)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppressions_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppressions")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"suppression_id", "status", "aging_score", "days_since_review"})

    report_aging = float(report.get("suppression_aging_score", 0.0))
    report_aging_count = int(report.get("aging_suppressions", 0))

    max_aging_score = 0.0
    aging_count = 0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in {"active", "approved"}:
            continue
        aging_score = _to_float(row.get("aging_score", ""), csv_path, "aging_score")
        max_aging_score = max(max_aging_score, aging_score)
        if aging_score > args.max_aging_score:
            aging_count += 1
        try:
            days = int((row.get("days_since_review") or "").strip() or 0)
        except ValueError as exc:
            _fail(f"D78 invalid days_since_review in {csv_path}: {exc}")
        if days > args.max_aging_days:
            aging_count += 1

    aging_count = max(aging_count, report_aging_count)
    effective_aging_score = max(max_aging_score, report_aging)

    if effective_aging_score > args.max_aging_score:
        _fail(f"D78 suppression aging gate failed: max_aging_score={effective_aging_score}")
    if aging_count > args.max_aging_suppressions:
        _fail(f"D78 suppression aging gate failed: aging_suppressions={aging_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

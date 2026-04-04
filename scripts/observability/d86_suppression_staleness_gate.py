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
        _fail(f"D86 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D86 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D86 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D86 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D86 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D86 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int((value or "").strip())
    except ValueError as exc:
        _fail(f"D86 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppressions-csv", required=True)
    parser.add_argument("--max-staleness-score", type=float, default=1.0)
    parser.add_argument("--max-stale-suppressions", type=int, default=0)
    parser.add_argument("--max-stale-days", type=int, default=30)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppressions_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppressions")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"suppression_id", "status", "staleness_score", "days_since_review"},
    )

    max_staleness = float(report.get("suppression_staleness_score", 0.0))
    stale_count = int(report.get("suppression_stale_count", 0))

    for row in rows:
        if (row.get("status") or "").strip().lower() not in {"active", "approved"}:
            continue
        max_staleness = max(
            max_staleness, _to_float(row.get("staleness_score", ""), csv_path, "staleness_score")
        )
        if _to_int(row.get("days_since_review", ""), csv_path, "days_since_review") > args.max_stale_days:
            stale_count += 1
        if _to_float(row.get("staleness_score", ""), csv_path, "staleness_score") > args.max_staleness_score:
            stale_count += 1

    if max_staleness > args.max_staleness_score:
        _fail(f"D86 suppression staleness gate failed: max_staleness_score={max_staleness}")
    if stale_count > args.max_stale_suppressions:
        _fail(f"D86 suppression staleness gate failed: stale_suppressions={stale_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

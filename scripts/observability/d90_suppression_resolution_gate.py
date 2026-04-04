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
        _fail(f"D90 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D90 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D90 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D90 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D90 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D90 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppressions-csv", required=True)
    parser.add_argument("--max-open-suppressions", type=int, default=0)
    parser.add_argument("--min-resolve-rate", type=float, default=1.0)
    parser.add_argument("--max-avg-resolve-time", type=float, default=0.0)
    parser.add_argument("--time-field", default="resolve_minutes")
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppressions_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppressions")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"suppression_id", "status", args.time_field},
    )

    resolved_count = 0
    unresolved_count = 0
    total_resolve = 0.0
    resolve_samples = 0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status in {"resolved", "closed", "dismissed", "acknowledged"}:
            resolved_count += 1
            minutes = row.get(args.time_field)
            if minutes is not None and str(minutes).strip():
                total_resolve += _to_float(minutes, csv_path, args.time_field)
                resolve_samples += 1
        else:
            unresolved_count += 1

    total_count = resolved_count + unresolved_count
    reported_unresolved = int(report.get("unresolved_suppressions", 0))
    reported_rate = float(report.get("suppression_resolve_rate", 1.0 if total_count else 0.0))
    reported_avg = float(report.get("avg_resolve_time", 0.0))

    row_avg = total_resolve / resolve_samples if resolve_samples else 0.0
    row_rate = (resolved_count / total_count) if total_count else 1.0

    effective_unresolved = max(unresolved_count, reported_unresolved)
    effective_rate = min(row_rate, reported_rate)
    effective_avg = max(row_avg, reported_avg)

    if effective_unresolved > args.max_open_suppressions:
        _fail(f"D90 suppression resolution gate failed: open_suppressions={effective_unresolved}")
    if effective_rate < args.min_resolve_rate:
        _fail(f"D90 suppression resolution gate failed: resolve_rate={effective_rate}")
    if effective_avg > args.max_avg_resolve_time:
        _fail(f"D90 suppression resolution gate failed: avg_resolve_time={effective_avg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        _fail(f"D82 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D82 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D82 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required_headers - set(reader.fieldnames or []))
            if missing:
                _fail(f"D82 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D82 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D82 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppressions-csv", required=True)
    parser.add_argument("--min-resolve-rate", type=float, default=0.95)
    parser.add_argument("--max-unresolved", type=int, default=0)
    parser.add_argument("--max-resolve-time", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppressions_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppressions")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"suppression_id", "status", "resolve_minutes"},
    )

    resolved = 0
    total = 0
    unresolved = int(report.get("unresolved_suppressions", 0))
    max_resolve = float(report.get("suppression_resolve_time", 0.0))

    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status in {"resolved", "closed", "dismissed"}:
            resolved += 1
        else:
            unresolved += 1
        total += 1
        raw = (row.get("resolve_minutes") or "").strip()
        if raw:
            max_resolve = max(max_resolve, _to_float(raw, csv_path, "resolve_minutes"))

    if total:
        row_rate = resolved / total
    else:
        row_rate = 1.0
    effective_rate = min(row_rate, float(report.get("suppression_resolve_rate", row_rate)))
    if max_resolve > args.max_resolve_time:
        _fail(f"D82 suppression resolve gate failed: max_resolve_time={max_resolve}")
    if unresolved > args.max_unresolved:
        _fail(f"D82 suppression resolve gate failed: unresolved={unresolved}")
    if effective_rate < args.min_resolve_rate:
        _fail(f"D82 suppression resolve gate failed: resolve_rate={effective_rate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        _fail(f"D73 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D73 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D73 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D73 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D73 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--max-fatigue-score", type=float, default=1.0)
    parser.add_argument("--max-fatigued-overrides", type=int, default=0)
    parser.add_argument("--max-stale-days", type=int, default=30)
    parser.add_argument("--max-stale-overrides", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"override_id", "status", "fatigue_score", "days_since_update"},
    )

    report_fatigue = float(report.get("override_fatigue_score", 0.0))
    row_fatigue_max = 0.0
    for row in rows:
        if (value := (row.get("fatigue_score") or "").strip()):
            row_fatigue_max = max(row_fatigue_max, float(value))
    fatigued = sum(
        1
        for row in rows
        if (row.get("status") or "").strip().lower() in {"active", "approved"}
        and float(row.get("fatigue_score", 0)) > args.max_fatigue_score
    )
    stale = sum(
        1
        for row in rows
        if int(row.get("days_since_update", 0) or 0) > args.max_stale_days
    )

    effective_fatigue = max(report_fatigue, row_fatigue_max)
    if effective_fatigue > args.max_fatigue_score:
        _fail(f"D73 override fatigue gate failed: fatigue_score={effective_fatigue}")
    if fatigued > args.max_fatigued_overrides:
        _fail(f"D73 override fatigue gate failed: fatigued_overrides={fatigued}")
    if stale > args.max_stale_overrides:
        _fail(f"D73 override fatigue gate failed: stale_overrides={stale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        _fail(f"D81 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D81 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D81 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required_headers - set(reader.fieldnames or []))
            if missing:
                _fail(f"D81 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D81 invalid CSV {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int((value or "").strip() or 0)
    except ValueError as exc:
        _fail(f"D81 invalid {field} in {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D81 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--max-debt-age", type=float, default=30.0)
    parser.add_argument("--max-stale-days", type=int, default=30)
    parser.add_argument("--max-debt-overrides", type=int, default=0)
    args = parser.parse_args()
    report_path = pathlib.Path(args.report)
    overrides_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(overrides_path, "overrides")
    report = _load_json(report_path)
    rows = _load_csv(
        overrides_path,
        {"override_id", "status", "debt_age_days", "days_since_update"},
    )

    report_debt_age = float(report.get("override_debt_age", 0.0))
    report_stale = int(report.get("stale_override_count", 0))

    max_debt_age = report_debt_age
    stale_count = report_stale
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in {"active", "approved"}:
            continue
        max_debt_age = max(
            max_debt_age,
            _to_float(row.get("debt_age_days", ""), overrides_path, "debt_age_days"),
        )
        if (
            _to_int(row.get("days_since_update", ""), overrides_path, "days_since_update")
            > args.max_stale_days
        ):
            stale_count += 1

    if max_debt_age > args.max_debt_age:
        _fail(f"D81 override debt age gate failed: max_debt_age={max_debt_age}")
    if stale_count > args.max_debt_overrides:
        _fail(f"D81 override debt age gate failed: stale_overrides={stale_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

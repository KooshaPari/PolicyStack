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
        _fail(f"D77 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D77 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D77 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D77 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D77 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D77 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--max-pressure-score", type=float, default=1.0)
    parser.add_argument("--max-pressured-overrides", type=int, default=0)
    parser.add_argument("--max-pressure-days", type=int, default=30)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"override_id", "status", "pressure_score", "days_since_update"})

    report_pressure = float(report.get("override_pressure_score", 0.0))
    report_pressure_count = int(report.get("pressured_overrides", 0))

    pressured_count = 0
    max_pressure = 0.0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in {"active", "approved"}:
            continue
        pressure = _to_float(row.get("pressure_score", ""), csv_path, "pressure_score")
        max_pressure = max(max_pressure, pressure)
        if pressure > args.max_pressure_score:
            pressured_count += 1
        if int((row.get("days_since_update") or "").strip() or 0) > args.max_pressure_days:
            pressured_count += 1

    pressured_count = max(pressured_count, report_pressure_count)
    effective_pressure = max(max_pressure, report_pressure)

    if effective_pressure > args.max_pressure_score:
        _fail(f"D77 override pressure gate failed: max_pressure_score={effective_pressure}")
    if pressured_count > args.max_pressured_overrides:
        _fail(f"D77 override pressure gate failed: pressured_overrides={pressured_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

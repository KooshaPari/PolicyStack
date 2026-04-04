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
        _fail(f"D85 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D85 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D85 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D85 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D85 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D85 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int((value or "").strip())
    except ValueError as exc:
        _fail(f"D85 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--max-age-pressure-score", type=float, default=1.0)
    parser.add_argument("--max-age-pressure-overrides", type=int, default=0)
    parser.add_argument("--max-pressure-age-days", type=int, default=30)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"override_id", "status", "pressure_score", "days_since_update"},
    )

    report_score = float(report.get("override_age_pressure_score", 0.0))
    report_breaches = int(report.get("override_age_pressure_breaches", 0))

    score = report_score
    breaches = report_breaches
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in {"active", "approved"}:
            continue
        pressure = _to_float(row.get("pressure_score", ""), csv_path, "pressure_score")
        days = _to_int(
            row.get("days_since_update", ""), csv_path, "days_since_update"
        )
        score = max(score, pressure)
        age_pressure = pressure * (1.0 + days / max(args.max_pressure_age_days, 1))
        if age_pressure > args.max_age_pressure_score:
            breaches += 1
        if days > args.max_pressure_age_days:
            breaches += 1

    if score > args.max_age_pressure_score:
        _fail(f"D85 override age pressure gate failed: max_age_pressure_score={score}")
    if breaches > args.max_age_pressure_overrides:
        _fail(
            f"D85 override age pressure gate failed: "
            f"overrides_exceeding_age_pressure={breaches}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

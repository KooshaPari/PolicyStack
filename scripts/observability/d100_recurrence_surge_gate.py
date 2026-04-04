#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D100 recurrence surge gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D100 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D100 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        _fail(f"D100 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                _fail(f"D100 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D100 invalid recurrence CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D100 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        _fail(f"D100 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--value-field", default="recurrence_count")
    parser.add_argument("--max-surge", type=float, default=0.0)
    parser.add_argument("--max-consecutive-surge", type=int, default=0)
    parser.add_argument("--max-surge-events", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field})
    if not rows:
        _fail("D100 recurrence surge gate failed: empty recurrence csv")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or "").strip())
    values = [
        _to_float(row.get(args.value_field, ""), csv_path, args.value_field)
        for row in ordered
    ]

    deltas = [after - before for before, after in zip(values, values[1:])]
    peaks = [delta for delta in deltas if delta > args.max_surge * 0.5]

    max_surge = max((abs(delta) for delta in deltas), default=0.0)
    max_surge_report = float(report.get("recurrence_surge", 0.0))
    if max_surge < max_surge_report:
        max_surge = max_surge_report

    surge_events = _to_int(
        str(report.get("recurrence_surge_events", 0)),
        report_path,
        "recurrence_surge_events",
    )
    max_consecutive = 0
    current = 0
    for delta in peaks:
        if delta > args.max_surge:
            surge_events += 1
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 0

    if max_surge > args.max_surge:
        _fail(f"D100 recurrence surge gate failed: max_surge={max_surge}")
    if max_consecutive > args.max_consecutive_surge:
        _fail(
            "D100 recurrence surge gate failed: "
            f"consecutive_surge_windows={max_consecutive}"
        )
    if surge_events > args.max_surge_events:
        _fail(f"D100 recurrence surge gate failed: surge_events={surge_events}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

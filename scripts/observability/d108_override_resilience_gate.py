#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D108 override resilience gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D108 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D108 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D108 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D108 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D108 invalid override CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D108 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        fail(f"D108 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--value-field", default="resilience")
    parser.add_argument("--count-field", default="open_overrides")
    parser.add_argument("--max-open-overrides", type=int, default=0)
    parser.add_argument("--max-resilience-drop", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field, args.count_field})
    if not rows:
        fail("D108 override resilience gate failed: no override rows")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    resilience = [_to_float(row.get(args.value_field, ""), csv_path, args.value_field) for row in ordered]
    open_counts = [_to_int(row.get(args.count_field, ""), csv_path, args.count_field) for row in ordered]

    max_open = max(open_counts)
    report_open = _to_int(str(report.get("override_open_count", 0)), report_path, "override_open_count")
    if max_open < report_open:
        max_open = report_open

    drops = [max(0.0, a - b) for a, b in zip(resilience, resilience[1:])]
    max_drop = max(drops, default=0.0)

    if max_open > args.max_open_overrides:
        fail(f"D108 max_open_overrides={max_open} > limit={args.max_open_overrides}")
    if max_drop > args.max_resilience_drop:
        fail(f"D108 max_resilience_drop={max_drop} > max_resilience_drop={args.max_resilience_drop}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

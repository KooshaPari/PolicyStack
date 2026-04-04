#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D106 suppression decay consistency gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D106 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D106 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D106 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D106 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D106 invalid suppression CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D106 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--value-field", default="decay_rate")
    parser.add_argument("--plateau-window", type=int, default=3)
    parser.add_argument("--max-plateau-count", type=int, default=0)
    parser.add_argument("--min-decay-rate", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppression_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppression")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field})
    if not rows:
        fail("D106 suppression decay consistency gate failed: empty suppression data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    values = [_to_float(row.get(args.value_field, ""), csv_path, args.value_field) for row in ordered]
    if len(values) < 3:
        fail("D106 suppression decay consistency gate failed: insufficient samples")

    drops = [a - b for a, b in zip(values, values[1:])]
    plateau_count = sum(1 for d in drops if abs(d) <= args.min_decay_rate)

    reported_plateau = int(report.get("suppression_decay_plateau_windows", 0))
    plateau_count = max(plateau_count, reported_plateau)

    if plateau_count > args.max_plateau_count:
        fail(f"D106 plateau_count={plateau_count} > max_plateau_count={args.max_plateau_count}")

    if args.plateau_window > 1:
        stale_windows = 0
        for idx in range(len(values) - args.plateau_window + 1):
            window = values[idx : idx + args.plateau_window]
            spread = max(window) - min(window)
            if spread <= args.min_decay_rate:
                stale_windows += 1
        if stale_windows > args.max_plateau_count:
            fail(f"D106 stale_windows={stale_windows} > max_plateau_count={args.max_plateau_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

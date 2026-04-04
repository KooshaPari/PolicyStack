#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D110 suppression entropy gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D110 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D110 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D110 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D110 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D110 invalid suppression CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D110 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--entropy-field", default="entropy")
    parser.add_argument("--min-entropy", type=float, default=0.0)
    parser.add_argument("--max-entropy-dip", type=float, default=0.0)
    parser.add_argument("--max-low-entropy-windows", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppression_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppression")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.entropy_field})
    if not rows:
        fail("D110 suppression entropy gate failed: empty suppression data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    entropies = [
        _to_float(row.get(args.entropy_field, ""), csv_path, args.entropy_field)
        for row in ordered
    ]
    if not entropies:
        fail("D110 suppression entropy gate failed: no entropy points")

    low_windows = sum(1 for value in entropies if value < args.min_entropy)
    dips = [a - b for a, b in zip(entropies, entropies[1:])]
    max_dip = max([abs(d) for d in dips], default=0.0)

    if args.min_entropy > 0:
        report_low = int(report.get("suppression_low_entropy_windows", 0))
        low_windows = max(low_windows, report_low)

    if low_windows > args.max_low_entropy_windows:
        fail(f"D110 low_entropy_windows={low_windows} > max_low_entropy_windows={args.max_low_entropy_windows}")

    if max_dip > args.max_entropy_dip:
        fail(f"D110 max_entropy_dip={max_dip} > max_entropy_dip={args.max_entropy_dip}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

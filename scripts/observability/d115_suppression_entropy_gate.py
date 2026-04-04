#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D115 suppression entropy gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D115 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D115 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D115 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D115 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D115 invalid suppression CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D115 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppression-csv", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--entropy-field", default="entropy")
    parser.add_argument("--max-entropy", type=float, default=0.0)
    parser.add_argument("--max-step-change", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppression_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppression")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.entropy_field})
    if not rows:
        fail("D115 suppression entropy gate failed: empty suppression data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    entropies = [_to_float(row.get(args.entropy_field, ""), csv_path, args.entropy_field) for row in ordered]
    max_entropy = max(entropies)

    if len(entropies) > 1:
        max_step_change = max(abs(a - b) for a, b in zip(entropies, entropies[1:]))
    else:
        max_step_change = 0.0

    report_entropy = float(report.get("suppression_entropy_max", 0.0))
    report_step = float(report.get("suppression_entropy_step_max", 0.0))
    if max_entropy < report_entropy:
        max_entropy = report_entropy
    if max_step_change < report_step:
        max_step_change = report_step

    if max_entropy > args.max_entropy:
        fail(f"D115 max_entropy={max_entropy} > max_entropy={args.max_entropy}")
    if max_step_change > args.max_step_change:
        fail(f"D115 max_step_change={max_step_change} > max_step_change={args.max_step_change}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

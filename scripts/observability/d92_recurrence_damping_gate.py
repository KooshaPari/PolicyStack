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
        _fail(f"D92 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D92 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D92 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D92 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D92 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D92 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--value-field", default="open_recurrence")
    parser.add_argument("--max-tail-amplitude", type=float, default=0.0)
    parser.add_argument("--max-damping-steps", type=int, default=0)
    parser.add_argument("--max-damping-duration", type=int, default=3)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {args.time_field, args.value_field})
    if not rows:
        _fail("D92 recurrence damping gate failed: empty recurrence csv")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or "").strip())
    values = [_to_float(row.get(args.value_field), csv_path, args.value_field) for row in ordered]

    max_tail = float(report.get("recurrence_damping_tail", 0.0))
    damping_steps = int(report.get("recurrence_damping_steps", 0))

    if len(values) < 2:
        max_amplitude = 0.0
    else:
        deltas = [abs(current - previous) for previous, current in zip(values, values[1:])]
        max_amplitude = max(deltas) if deltas else 0.0
        for first, second in zip(values, values[1:]):
            if abs(second - first) > 0:
                damping_steps += 1

    effective_tail = max(max_amplitude, max_tail)
    if effective_tail > args.max_tail_amplitude:
        _fail(f"D92 recurrence damping gate failed: max_tail_amplitude={effective_tail}")

    if damping_steps > args.max_damping_steps:
        _fail(f"D92 recurrence damping gate failed: damping_steps={damping_steps}")

    if len(values) > max(1, args.max_damping_duration):
        tail = values[-args.max_damping_duration :]
        baseline = sum(values[:-args.max_damping_duration]) / (
            len(values) - args.max_damping_duration
        )
        tail_avg = sum(tail) / len(tail)
        bias = abs(tail_avg - baseline)
        if bias > max_tail:
            _fail(f"D92 recurrence damping gate failed: tail_bias={bias}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

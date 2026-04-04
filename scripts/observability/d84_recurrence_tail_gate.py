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
        _fail(f"D84 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D84 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D84 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required_headers - set(reader.fieldnames or []))
            if missing:
                _fail(f"D84 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D84 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D84 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--tail-size", type=int, default=3)
    parser.add_argument("--max-tail-recurrence", type=float, default=0.0)
    parser.add_argument("--max-tail-spikes", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"window_start", "open_recurrence"})
    if not rows:
        _fail("D84 recurrence tail gate failed: empty recurrence csv")

    windows = sorted(rows, key=lambda row: (row.get("window_start") or "").strip())
    tail = windows[-args.tail_size :] if args.tail_size > 0 else windows
    tail_values = [
        _to_float(r.get("open_recurrence", ""), csv_path, "open_recurrence")
        for r in tail
    ]

    max_tail = max(tail_values)
    tail_spikes = 0
    for previous, current in zip(tail_values, tail_values[1:]):
        if current > previous:
            tail_spikes += 1

    effective_tail = max(
        max_tail,
        float(report.get("recurrence_tail_max", 0.0)),
    )
    effective_spikes = max(
        tail_spikes,
        int(report.get("recurrence_tail_spikes", 0)),
    )
    if effective_tail > args.max_tail_recurrence:
        _fail(f"D84 recurrence tail gate failed: max_tail_recurrence={effective_tail}")
    if effective_spikes > args.max_tail_spikes:
        _fail(f"D84 recurrence tail gate failed: tail_spikes={effective_spikes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

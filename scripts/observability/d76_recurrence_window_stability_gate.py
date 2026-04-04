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
        _fail(f"D76 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D76 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D76 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D76 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D76 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--window-csv", required=True)
    parser.add_argument("--max-window-variance", type=float, default=0.0)
    parser.add_argument("--max-window-worsen-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.window_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "window")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"window_start", "open_recurrence", "closed_recurrence"},
    )
    if not rows:
        _fail("D76 recurrence window stability gate failed: empty window csv")

    sorted_rows = sorted(
        rows,
        key=lambda row: (row.get("window_start") or "").strip(),
    )

    report_variance = float(report.get("recurrence_window_variance", 0.0))
    report_worsening = int(report.get("recurrence_window_worsening_events", 0))

    values = []
    worsening = 0
    for row in sorted_rows:
        try:
            values.append(float((row.get("open_recurrence") or "").strip()))
        except ValueError as exc:
            _fail(f"D76 recurrence window stability gate failed: invalid open_recurrence value: {exc}")
    for previous, current in zip(values, values[1:]):
        if current > previous:
            worsening += 1

    variance = max(
        values[i + 1] - values[i] for i in range(len(values) - 1)
    ) if len(values) > 1 else 0.0
    max_variance = max(report_variance, variance)
    worsening = max(worsening, report_worsening)

    if max_variance > args.max_window_variance:
        _fail(
            f"D76 recurrence window stability gate failed: "
            f"max_window_variance={max_variance}"
        )
    if worsening > args.max_window_worsen_count:
        _fail(f"D76 recurrence window stability gate failed: worsening_windows={worsening}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

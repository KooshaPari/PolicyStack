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
        _fail(f"D87 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D87 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D87 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D87 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D87 invalid CSV {path}: {exc}")
    return rows


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D87 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--max-burst-score", type=float, default=1.0)
    parser.add_argument("--max-burst-events", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"escalation_id", "status", "burst_score", "window_start"},
    )

    max_burst = float(report.get("escalation_burst_score", 0.0))
    burst_events = int(report.get("escalation_burst_events", 0))

    status_filter = {"open", "active", "in_progress"}
    for row in sorted(rows, key=lambda row: (row.get("window_start") or "").strip()):
        if (row.get("status") or "").strip().lower() not in status_filter:
            continue
        burst = _to_float(row.get("burst_score", ""), csv_path, "burst_score")
        max_burst = max(max_burst, burst)
        if burst > args.max_burst_score:
            burst_events += 1

    if max_burst > args.max_burst_score:
        _fail(f"D87 escalation burst gate failed: max_burst_score={max_burst}")
    if burst_events > args.max_burst_events:
        _fail(f"D87 escalation burst gate failed: burst_events={burst_events}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

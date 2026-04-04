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
        _fail(f"D75 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D75 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D75 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D75 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D75 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--max-backoff-level", type=float, default=1200.0)
    parser.add_argument("--max-backoff-breaches", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"escalation_id", "status", "backoff_seconds", "failure_count"},
    )

    report_level = float(report.get("escalation_backoff_seconds", 0.0))
    report_breaches = int(report.get("escalation_backoff_breaches", 0))

    max_backoff = 0.0
    for row in rows:
        if (value := (row.get("backoff_seconds") or "").strip()):
            max_backoff = max(max_backoff, float(value))
    breaches = sum(
        1
        for row in rows
        if (row.get("status") or "").strip().lower() == "throttled"
        and float(row.get("backoff_seconds", 0) or 0) > args.max_backoff_level
    )

    breaches = max(breaches, report_breaches)
    effective_backoff = max(report_level, max_backoff)

    if effective_backoff > args.max_backoff_level:
        _fail(
            f"D75 escalation backoff gate failed: "
            f"backoff_seconds={effective_backoff}"
        )
    if breaches > args.max_backoff_breaches:
        _fail(f"D75 escalation backoff gate failed: breaches={breaches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

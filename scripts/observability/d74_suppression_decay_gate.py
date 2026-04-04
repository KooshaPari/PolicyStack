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
        _fail(f"D74 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D74 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D74 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D74 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D74 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppressions-csv", required=True)
    parser.add_argument("--max-decayed-suppressions", type=int, default=0)
    parser.add_argument("--max-decay-days", type=int, default=30)
    parser.add_argument("--max-decay-score", type=float, default=1.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppressions_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppressions")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"suppression_id", "status", "days_since_review", "decay_score"},
    )

    report_decay_score = float(report.get("suppression_decay_score", 0.0))
    report_decay_count = int(report.get("suppression_decay_count", 0))

    decayed = sum(
        1
        for row in rows
        if (row.get("status") or "").strip().lower() in {"active", "approved"}
        and int(row.get("days_since_review", 0) or 0) > args.max_decay_days
    )
    max_decay_score = 0.0
    for row in rows:
        if (value := (row.get("decay_score") or "").strip()):
            max_decay_score = max(max_decay_score, float(value))

    decayed = max(decayed, report_decay_count)
    effective_decay_score = max(report_decay_score, max_decay_score)

    if effective_decay_score > args.max_decay_score:
        _fail(f"D74 suppression decay gate failed: decay_score={effective_decay_score}")
    if decayed > args.max_decayed_suppressions:
        _fail(f"D74 suppression decay gate failed: decayed_suppressions={decayed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

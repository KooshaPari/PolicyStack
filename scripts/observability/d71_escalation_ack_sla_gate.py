#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> "None":
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D71 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D71 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D71 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D71 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D71 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--ack-sla-minutes", type=float, default=30.0)
    parser.add_argument("--max-sla-breaches", type=int, default=0)
    args = parser.parse_args()

    metrics_path = pathlib.Path(args.metrics)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(metrics_path, "metrics")
    _require_file(csv_path, "escalations")

    metrics = _load_json(metrics_path)
    rows = _load_csv(
        csv_path,
        {"incident_id", "ack_minutes"},
    )

    breaches = 0
    for row in rows:
        raw = (row.get("ack_minutes") or "").strip()
        try:
            ack_minutes = float(raw)
        except ValueError:
            breaches += 1
            continue
        if ack_minutes > args.ack_sla_minutes:
            breaches += 1

    breaches = max(breaches, int(metrics.get("escalation_ack_sla_breaches", 0)))
    if breaches > args.max_sla_breaches:
        _fail(f"D71 escalation ack SLA gate failed: breaches={breaches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

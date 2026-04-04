#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D95 escalation stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"invalid report JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail("report must be object")
    return data


def _to_int(value: object, field: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        _fail(f"invalid integer {field}: {value!r}")


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except Exception:
        _fail(f"invalid float {field}: {value!r}")

parser = argparse.ArgumentParser()
parser.add_argument("--report", required=True)
parser.add_argument("--events-csv", required=True)
parser.add_argument("--max-reopens", type=int, default=0)
parser.add_argument("--max-burstes", type=int, default=0)
parser.add_argument("--max-duplication", type=float, default=0.0)
args = parser.parse_args()

report = _load_json(pathlib.Path(args.report))
rows = list(csv.DictReader(pathlib.Path(args.events_csv).read_text().splitlines()))

reopens = _to_int(report.get("escalation_reopens", 0), "escalation_reopens")
if reopens > args.max_reopens:
    _fail(f"escalation_reopens={reopens}")

bursts = _to_int(report.get("burst_count", 0), "burst_count")
if bursts > args.max_burstes:
    _fail(f"burst_count={bursts}")

duplicates = 0
seen = set()
for row in rows:
    key = json.dumps(row, sort_keys=True)
    if key in seen:
        duplicates += 1
    seen.add(key)
dup_ratio = float(duplicates) / max(1, len(rows))
if dup_ratio > args.max_duplication:
    _fail(f"duplication_ratio={dup_ratio}")


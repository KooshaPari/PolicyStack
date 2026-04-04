#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D96 recurrence acceleration gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except Exception:
        _fail(f"invalid float {field}: {value!r}")


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(path.read_text().splitlines()))
    except Exception as exc:
        _fail(f"invalid recurrence CSV {path}: {exc}")
    if rows and required and not required.issubset(set(rows[0].keys())):
        _fail(f"recurrence CSV missing headers: {sorted(required - set(rows[0].keys()))}")
    return rows

parser = argparse.ArgumentParser()
parser.add_argument("--report", required=True)
parser.add_argument("--recurrence-csv", required=True)
parser.add_argument("--value-field", default="acceleration")
parser.add_argument("--max-acceleration", type=float, default=0.0)
parser.add_argument("--max-positive-deltas", type=int, default=0)
parser.add_argument("--max-accumulated", type=float, default=0.0)
args = parser.parse_args()

payload = json.loads(pathlib.Path(args.report).read_text()) if pathlib.Path(args.report).is_file() else {}
if not isinstance(payload, dict):
    _fail("invalid report JSON")

target = args.value_field
rows = _read_csv(pathlib.Path(args.recurrence_csv), {target})
if not rows:
    _fail("empty recurrence csv")

accs = [_to_float(row.get(target), target) for row in rows]
positive_steps = sum(1 for x in accs[1:] if x > 0)
max_acc = max(accs)
accum = sum(accs)

if max_acc > args.max_acceleration:
    _fail(f"max_acceleration={max_acc}")
if positive_steps > args.max_positive_deltas:
    _fail(f"positive_steps={positive_steps}")
if accum > args.max_accumulated:
    _fail(f"accumulated_acceleration={accum}")


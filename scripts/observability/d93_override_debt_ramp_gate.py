#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D93 override debt ramp gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"JSON payload must be object: {path}")
    return data


def _load_rows(path: pathlib.Path) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(path.read_text().splitlines()))
    except Exception as exc:
        _fail(f"invalid CSV {path}: {exc}")
    return rows


def _to_int(value: object, field: str) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        _fail(f"invalid integer in {field}: {value!r}")


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        _fail(f"invalid float in {field}: {value!r}")

parser = argparse.ArgumentParser()
parser.add_argument("--report", required=True)
parser.add_argument("--debt-csv", required=True)
parser.add_argument("--value-field", default="debt")
parser.add_argument("--window-field", default="window")
parser.add_argument("--max-ramp-rate", type=float, default=0.0)
parser.add_argument("--max-step-count", type=int, default=0)
parser.add_argument("--max-debt", type=int, default=0)
args = parser.parse_args()

report = _load_json(pathlib.Path(args.report))
rows = _load_rows(pathlib.Path(args.debt_csv))

if not rows:
    _fail("empty debt CSV")

values = [_to_int(row.get(args.value_field), args.value_field) for row in rows]
debt_max = max(values)
max_reported = _to_int(report.get("max_debt", report.get("debt_peak", 0)), "max_debt")

ramp_steps = 0
max_ramp = 0.0
for a, b in zip(values, values[1:]):
    delta = abs(b - a)
    max_ramp = max(max_ramp, float(delta))
    if delta > 0:
        ramp_steps += 1

if max_reported != debt_max:
    _fail(f"debt_max mismatch report={max_reported} observed={debt_max}")

if max_ramp > args.max_ramp_rate:
    _fail(f"max_ramp_rate={max_ramp}")
if ramp_steps > args.max_step_count:
    _fail(f"ramp_steps={ramp_steps}")
if debt_max > args.max_debt:
    _fail(f"debt_max={debt_max}")


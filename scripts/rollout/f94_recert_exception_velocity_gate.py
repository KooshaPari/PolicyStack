#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"F94 recert exception velocity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


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
parser.add_argument("--recert", required=True)
parser.add_argument("--max-exception-velocity", type=float, default=0.0)
parser.add_argument("--max-burst-cycles", type=int, default=0)
parser.add_argument("--max-open-exceptions", type=int, default=0)
args = parser.parse_args()

report = json.loads(pathlib.Path(args.recert).read_text())
if not isinstance(report, dict):
    _fail("recert report must be object")

velocity = _to_float(report.get("exception_velocity", report.get("velocity", 0.0)), "exception_velocity")
burst = _to_int(report.get("velocity_burst", report.get("burst_cycles", 0)), "velocity_burst")
open_ex = _to_int(report.get("open_exceptions", report.get("open", 0)), "open_exceptions")

if velocity > args.max_exception_velocity:
    _fail(f"exception_velocity={velocity}")
if burst > args.max_burst_cycles:
    _fail(f"burst_cycles={burst}")
if open_ex > args.max_open_exceptions:
    _fail(f"open_exceptions={open_ex}")

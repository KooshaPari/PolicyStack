#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D94 suppression tolerance gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        _fail("report must be JSON object")
    return payload


def _read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    try:
        return list(csv.DictReader(path.read_text().splitlines()))
    except Exception as exc:
        _fail(f"invalid suppression CSV {path}: {exc}")


def _to_int(value: object, field: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        _fail(f"invalid integer {field}: {value!r}")

parser = argparse.ArgumentParser()
parser.add_argument("--report", required=True)
parser.add_argument("--suppressions", required=True)
parser.add_argument("--max-hard-suppression", type=int, default=0)
parser.add_argument("--max-flap-ratio", type=float, default=0.0)
parser.add_argument("--max-noise-score", type=float, default=0.0)
args = parser.parse_args()

report = _read_json(pathlib.Path(args.report))
rows = _read_csv(pathlib.Path(args.suppressions))

hard = _to_int(report.get("hard_suppression_count", report.get("hard_count", 0)), "hard_suppression_count")
if hard > args.max_hard_suppression:
    _fail(f"hard_suppression_count={hard}")

flap_ratio = float(report.get("flap_ratio", report.get("suppression_flap_ratio", 0.0) or 0.0))
if flap_ratio > args.max_flap_ratio:
    _fail(f"flap_ratio={flap_ratio}")

noise_values = []
for row in rows:
    if "noise_score" in row:
        noise_values.append(float(str(row["noise_score"] or 0.0)))
if noise_values:
    max_noise = max(noise_values)
    if max_noise > args.max_noise_score:
        _fail(f"max_noise_score={max_noise}")


#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def parse_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


p = argparse.ArgumentParser()
p.add_argument("--stats", required=True)
p.add_argument("--total-key", default="preflight_total")
p.add_argument("--integrity-key", default="preflight_integrity_passed")
p.add_argument("--min-integrity-ratio", type=float, default=1.0)
a = p.parse_args()

stats = parse_json(pathlib.Path(a.stats))
total = float(stats.get(a.total_key, 0.0) or 0.0)
integrity = float(stats.get(a.integrity_key, 0.0) or 0.0)
integrity_ratio = (integrity / total) if total > 0 else 1.0

if integrity_ratio < a.min_integrity_ratio:
    print("B82 signature preflight integrity gate failed", file=sys.stderr)
    raise SystemExit(2)

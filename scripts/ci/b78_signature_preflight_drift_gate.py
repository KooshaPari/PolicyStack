#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


p = argparse.ArgumentParser()
p.add_argument("--stats", required=True)
p.add_argument("--total-key", default="preflight_total")
p.add_argument("--drift-key", default="preflight_drift")
p.add_argument("--max-drift-rate", type=float, default=0.0)
a = p.parse_args()

stats = json.loads(pathlib.Path(a.stats).read_text())
total = float(stats.get(a.total_key, 0.0) or 0.0)
drift = float(stats.get(a.drift_key, 0.0) or 0.0)
drift_rate = (drift / total) if total > 0 else 0.0
if drift_rate > a.max_drift_rate:
    print("B78 signature preflight drift gate failed", file=sys.stderr)
    raise SystemExit(2)


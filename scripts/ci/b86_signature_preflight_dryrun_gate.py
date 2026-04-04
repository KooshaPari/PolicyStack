#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


p = argparse.ArgumentParser()
p.add_argument("--stats", required=True)
p.add_argument("--dryrun-key", default="preflight_dryrun")
p.add_argument("--total-key", default="preflight_total")
p.add_argument("--max-dryrun-rate", type=float, default=0.0)
a = p.parse_args()

stats = json.loads(pathlib.Path(a.stats).read_text())
dryrun = float(stats.get(a.dryrun_key, 0.0) or 0.0)
total = float(stats.get(a.total_key, 0.0) or 0.0)
dryrun_rate = (dryrun / total) if total > 0 else 0.0

if dryrun_rate > a.max_dryrun_rate:
    print("B86 signature preflight dryrun gate failed", file=sys.stderr)
    raise SystemExit(2)

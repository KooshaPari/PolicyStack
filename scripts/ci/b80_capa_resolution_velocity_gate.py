#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


p = argparse.ArgumentParser()
p.add_argument("--csv", required=True)
p.add_argument("--resolved-col", default="resolved_count")
p.add_argument("--opened-col", default="opened_count")
p.add_argument("--min-velocity", type=float, default=0.0)
p.add_argument("--max-breaches", type=int, default=0)
a = p.parse_args()

rows = list(csv.DictReader(pathlib.Path(a.csv).read_text().splitlines()))
breaches = 0
for row in rows:
    opened = float(row.get(a.opened_col, 0.0) or 0.0)
    resolved = float(row.get(a.resolved_col, 0.0) or 0.0)
    velocity = (resolved / opened) if opened > 0 else 0.0
    if velocity < a.min_velocity:
        breaches += 1

if breaches > a.max_breaches:
    print("B80 CAPA resolution velocity gate failed", file=sys.stderr)
    raise SystemExit(2)


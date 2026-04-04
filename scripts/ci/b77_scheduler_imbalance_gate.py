#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


p = argparse.ArgumentParser()
p.add_argument("--csv", required=True)
p.add_argument("--value-col", default="imbalance")
p.add_argument("--max-imbalance", type=float, default=0.0)
p.add_argument("--max-breaches", type=int, default=0)
a = p.parse_args()

rows = list(csv.DictReader(pathlib.Path(a.csv).read_text().splitlines()))
breaches = sum(
    1
    for r in rows
    if abs(float(r.get(a.value_col, 0) or 0.0)) > a.max_imbalance
)
if breaches > a.max_breaches:
    print("B77 scheduler imbalance gate failed", file=sys.stderr)
    raise SystemExit(2)


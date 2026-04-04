#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def parse_csv(path: pathlib.Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text().splitlines()))


p = argparse.ArgumentParser()
p.add_argument("--csv", required=True)
p.add_argument("--reopened-col", default="reopened_count")
p.add_argument("--closed-col", default="closed_count")
p.add_argument("--target-reopen-rate", type=float, default=0.0)
p.add_argument("--max-variance", type=float, default=0.0)
p.add_argument("--max-breaches", type=int, default=0)
a = p.parse_args()

rows = parse_csv(pathlib.Path(a.csv))
breaches = 0
for row in rows:
    reopened = float(row.get(a.reopened_col, 0.0) or 0.0)
    closed = float(row.get(a.closed_col, 0.0) or 0.0)
    if closed <= 0:
        continue
    reopen_rate = reopened / closed
    if abs(reopen_rate - a.target_reopen_rate) > a.max_variance:
        breaches += 1

if breaches > a.max_breaches:
    print("B85 capability reopen stability gate failed", file=sys.stderr)
    raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def parse_csv(path: pathlib.Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text().splitlines()))


p = argparse.ArgumentParser()
p.add_argument("--csv", required=True)
p.add_argument("--value-col", default="safety_value")
p.add_argument("--floor-col", default="safety_floor")
p.add_argument("--max-breaches", type=int, default=0)
a = p.parse_args()

rows = parse_csv(pathlib.Path(a.csv))
breaches = sum(
    1
    for r in rows
    if float(r.get(a.value_col, 0.0) or 0.0) < float(r.get(a.floor_col, 0.0) or 0.0)
)

if breaches > a.max_breaches:
    print("B81 scheduler safety floor gate failed", file=sys.stderr)
    raise SystemExit(2)

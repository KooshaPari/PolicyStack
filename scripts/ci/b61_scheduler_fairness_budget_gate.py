#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); p.add_argument('--max-var', type=float, default=0.25); a=p.parse_args()
rows=list(csv.DictReader(pathlib.Path(a.csv).read_text().splitlines()))
if any(float(r.get('wait_variance',0.0))>a.max_var for r in rows):
    print('B61 scheduler fairness budget failed', file=sys.stderr); raise SystemExit(2)

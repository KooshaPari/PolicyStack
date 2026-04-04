#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); p.add_argument('--max-var', type=float, default=0.25); a=p.parse_args()
rows=list(csv.DictReader(pathlib.Path(a.csv).open()))
for r in rows:
    if float(r.get('wait_variance',0))>a.max_var:
        print('B57 fairness regression', file=sys.stderr); raise SystemExit(2)

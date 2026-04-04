#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); p.add_argument('--breach-col', default='slo_breach'); p.add_argument('--max-breaches', type=int, default=0); a=p.parse_args()
rows=list(csv.DictReader(pathlib.Path(a.csv).open()))
breaches=sum(int(float(r.get(a.breach_col,0) or 0)) for r in rows)
if breaches>a.max_breaches:
    print('B65 scheduler fairness SLO gate failed', file=sys.stderr); raise SystemExit(2)

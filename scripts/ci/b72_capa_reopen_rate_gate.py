#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); p.add_argument('--reopened-col', default='reopened_count'); p.add_argument('--closed-col', default='closed_count'); p.add_argument('--max-rate', type=float, default=0.0); a=p.parse_args()
rows=list(csv.DictReader(pathlib.Path(a.csv).open()))
reopened=sum(float(r.get(a.reopened_col,0) or 0) for r in rows); closed=sum(float(r.get(a.closed_col,0) or 0) for r in rows); rate=(reopened/closed) if closed>0 else 0.0
if rate>a.max_rate:
    print('B72 CAPA reopen rate gate failed', file=sys.stderr); raise SystemExit(2)

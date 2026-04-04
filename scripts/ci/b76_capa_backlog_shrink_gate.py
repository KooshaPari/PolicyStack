#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); p.add_argument('--before-col', default='backlog_before'); p.add_argument('--after-col', default='backlog_after'); p.add_argument('--min-shrink-rate', type=float, default=0.0); a=p.parse_args()
rows=list(csv.DictReader(pathlib.Path(a.csv).open()))
before=sum(float(r.get(a.before_col,0) or 0) for r in rows); after=sum(float(r.get(a.after_col,0) or 0) for r in rows)
shrink=(before-after)/before if before>0 else 0.0
if shrink<a.min_shrink_rate:
    print('B76 CAPA backlog shrink gate failed', file=sys.stderr)
    raise SystemExit(2)

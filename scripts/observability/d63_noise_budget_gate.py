#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); p.add_argument('--max-noise', type=float, default=0.2); a=p.parse_args()
rows=list(csv.DictReader(pathlib.Path(a.csv).read_text().splitlines()))
if any(float(r.get('noise_ratio',0.0))>a.max_noise for r in rows):
    print('D63 noise budget breach', file=sys.stderr); raise SystemExit(2)

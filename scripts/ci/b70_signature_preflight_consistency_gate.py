#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--stats', required=True); p.add_argument('--total-key', default='preflight_total'); p.add_argument('--consistent-key', default='preflight_consistent'); p.add_argument('--min-ratio', type=float, default=1.0); a=p.parse_args()
s=json.loads(pathlib.Path(a.stats).read_text())
total=float(s.get(a.total_key,0) or 0); consistent=float(s.get(a.consistent_key,0) or 0); ratio=(consistent/total) if total>0 else 1.0
if ratio<a.min_ratio:
    print('B70 signature preflight consistency gate failed', file=sys.stderr); raise SystemExit(2)

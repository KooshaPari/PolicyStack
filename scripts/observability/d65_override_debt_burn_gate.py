#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--min-burn-rate', type=float, default=1.0); a=p.parse_args()
f=pathlib.Path(a.metrics)
if not f.is_file():
    print(f'D65 missing metrics file: {f}', file=sys.stderr); raise SystemExit(2)
m=json.loads(f.read_text())
if float(m.get('override_debt_burn_rate',0.0))<a.min_burn_rate:
    print('D65 override debt burn gate failed', file=sys.stderr); raise SystemExit(2)


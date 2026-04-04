#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--stats', required=True); p.add_argument('--used-key', default='flake_budget_used'); p.add_argument('--limit-key', default='flake_budget_limit'); a=p.parse_args()
s=json.loads(pathlib.Path(a.stats).read_text())
if float(s.get(a.used_key,0))>float(s.get(a.limit_key,0)):
    print('B66 signature flake budget gate failed', file=sys.stderr); raise SystemExit(2)

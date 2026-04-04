#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--stats', required=True); p.add_argument('--max-flake-rate', type=float, default=0.003); a=p.parse_args()
s=json.loads(pathlib.Path(a.stats).read_text())
if float(s.get('flake_rate',0))>a.max_flake_rate:
    print('B58 flaky signature rate too high', file=sys.stderr); raise SystemExit(2)

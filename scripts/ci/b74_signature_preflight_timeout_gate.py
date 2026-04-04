#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--stats', required=True); p.add_argument('--timeout-key', default='preflight_timeouts'); p.add_argument('--total-key', default='preflight_total'); p.add_argument('--max-rate', type=float, default=0.0); a=p.parse_args()
s=json.loads(pathlib.Path(a.stats).read_text())
timeout=float(s.get(a.timeout_key,0) or 0); total=float(s.get(a.total_key,0) or 0); rate=(timeout/total) if total>0 else 0.0
if rate>a.max_rate:
    print('B74 signature preflight timeout gate failed', file=sys.stderr); raise SystemExit(2)

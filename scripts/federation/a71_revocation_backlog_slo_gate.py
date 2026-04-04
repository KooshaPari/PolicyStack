#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
def load(p):
    t=pathlib.Path(p).read_text()
    if str(p).lower().endswith('.csv'):
        r=list(csv.DictReader(t.splitlines())); return r[0] if r else {}
    return json.loads(t)
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-backlog', type=int, default=0); p.add_argument('--max-oldest-minutes', type=float, default=0.0); a=p.parse_args()
m=load(a.metrics)
backlog=int(float(m.get('revocation_backlog',m.get('backlog',0))))
oldest=float(m.get('revocation_backlog_oldest_minutes',m.get('oldest_minutes',0.0)))
if backlog>a.max_backlog or oldest>a.max_oldest_minutes:
    print('A71 revocation backlog slo gate failed', file=sys.stderr); raise SystemExit(2)

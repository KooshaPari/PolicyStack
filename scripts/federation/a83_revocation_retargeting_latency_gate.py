#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
def load(path):
    raw=pathlib.Path(path).read_text()
    if str(path).lower().endswith('.csv'):
        rows=list(csv.DictReader(raw.splitlines())); return rows[0] if rows else {}
    return json.loads(raw)
parser=argparse.ArgumentParser()
parser.add_argument('--latency', required=True)
parser.add_argument('--max-p95-ms', type=float, default=150.0)
parser.add_argument('--max-p99-ms', type=float, default=500.0)
args=parser.parse_args()
l=load(args.latency)
p95=float(l.get('retargeting_p95_ms', l.get('revocation_retargeting_p95_ms', l.get('p95_ms', 0))))
p99=float(l.get('retargeting_p99_ms', l.get('revocation_retargeting_p99_ms', l.get('p99_ms', 0))))
if p95 > args.max_p95_ms or p99 > args.max_p99_ms:
    print('A83 revocation retargeting latency gate failed', file=sys.stderr); raise SystemExit(2)

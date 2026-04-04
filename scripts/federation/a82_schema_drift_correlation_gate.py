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
parser.add_argument('--report', required=True)
parser.add_argument('--max-uncorrelated-ratio', type=float, default=0.25)
parser.add_argument('--max-unmatched-drift', type=int, default=0)
args=parser.parse_args()
r=load(args.report)
total=int(float(r.get('schema_drift_events', r.get('drift_events', r.get('total_drift_events', 0)))))
matched=int(float(r.get('correlated_drift_events', r.get('matched_drift_events', r.get('schema_drift_correlated', 0)))))
unmatched=int(float(r.get('uncorrelated_drift_events', r.get('unmatched_drift_events', total - matched))))
if total < 0 or unmatched > args.max_unmatched_drift:
    print('A82 schema drift correlation gate failed', file=sys.stderr); raise SystemExit(2)
ratio= (unmatched/total) if total else 0.0
if ratio > args.max_uncorrelated_ratio:
    print('A82 schema drift correlation gate failed', file=sys.stderr); raise SystemExit(2)

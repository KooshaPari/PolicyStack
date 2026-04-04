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
parser.add_argument('--max-window-minutes', type=float, default=120.0)
parser.add_argument('--max-window-hours', type=float, default=2.0)
args=parser.parse_args()
data=load(args.report)
window=float(data.get('rollback_window_minutes', data.get('cutover_rollback_window_minutes', data.get('rollback_window', 0))))
if window > args.max_window_minutes or window > args.max_window_hours * 60:
    print('A81 cutover rollback window gate failed', file=sys.stderr)
    raise SystemExit(2)

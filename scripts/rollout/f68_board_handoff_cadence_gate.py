#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--board', required=True); p.add_argument('--handoff-csv', required=True); p.add_argument('--max-days-since-handoff', type=int, default=30); a=p.parse_args()
b=json.loads(pathlib.Path(a.board).read_text())
if not isinstance(b, dict):
    print('F68 board handoff cadence gate failed: invalid board json', file=sys.stderr); raise SystemExit(2)
if int(b.get('days_since_last_handoff', 9999))>a.max_days_since_handoff:
    print('F68 board handoff cadence gate failed: board days_since_last_handoff exceeded', file=sys.stderr); raise SystemExit(2)
h=list(csv.DictReader(pathlib.Path(a.handoff_csv).read_text().splitlines()))
if not h or list(h[0].keys())!=['handoff_id','status','days_since_handoff']:
    print('F68 board handoff cadence gate failed: invalid handoff csv header', file=sys.stderr); raise SystemExit(2)
o=sum(1 for x in h if (x.get('status') or '').strip().lower()!='complete' or int((x.get('days_since_handoff') or '9999').strip())>a.max_days_since_handoff)
if o>0:
    print(f'F68 board handoff cadence gate failed: noncompliant_handoffs={o}', file=sys.stderr); raise SystemExit(2)

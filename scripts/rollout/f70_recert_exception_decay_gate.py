#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--recert', required=True); p.add_argument('--exceptions-csv', required=True); p.add_argument('--max-decay-days', type=int, default=30); a=p.parse_args()
r=json.loads(pathlib.Path(a.recert).read_text())
if not isinstance(r, dict):
    print('F70 recert exception decay gate failed: invalid recert json', file=sys.stderr); raise SystemExit(2)
if bool(r.get('exception_decay_enforced', True)) is not True:
    print('F70 recert exception decay gate failed: exception_decay_enforced != true', file=sys.stderr); raise SystemExit(2)
x=list(csv.DictReader(pathlib.Path(a.exceptions_csv).read_text().splitlines()))
if not x or list(x[0].keys())!=['exception_id','status','days_since_last_review']:
    print('F70 recert exception decay gate failed: invalid exceptions csv header', file=sys.stderr); raise SystemExit(2)
d=sum(1 for e in x if (e.get('status') or '').strip().lower() in {'active','approved'} and int((e.get('days_since_last_review') or '9999').strip())>a.max_decay_days)
if d>0:
    print(f'F70 recert exception decay gate failed: decayed_exceptions={d}', file=sys.stderr); raise SystemExit(2)

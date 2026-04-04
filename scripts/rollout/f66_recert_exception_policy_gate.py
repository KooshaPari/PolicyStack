#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--recert', required=True); p.add_argument('--exceptions-csv', required=True); p.add_argument('--max-policy-violations', type=int, default=0); a=p.parse_args()
r=json.loads(pathlib.Path(a.recert).read_text())
if not isinstance(r, dict):
    print('F66 recert exception policy gate failed: invalid recert json', file=sys.stderr); raise SystemExit(2)
if bool(r.get('policy_review_complete', True)) is not True:
    print('F66 recert exception policy gate failed: policy_review_complete != true', file=sys.stderr); raise SystemExit(2)
x=list(csv.DictReader(pathlib.Path(a.exceptions_csv).read_text().splitlines()))
if not x or list(x[0].keys())!=['exception_id','policy_status','owner']:
    print('F66 recert exception policy gate failed: invalid exceptions csv header', file=sys.stderr); raise SystemExit(2)
v=sum(1 for e in x if (e.get('policy_status') or '').strip().lower()!='compliant')
if v>a.max_policy_violations:
    print(f'F66 recert exception policy gate failed: policy_violations={v} > {a.max_policy_violations}', file=sys.stderr); raise SystemExit(2)


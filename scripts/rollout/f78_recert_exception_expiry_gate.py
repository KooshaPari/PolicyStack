#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--recert', required=True); p.add_argument('--exceptions-csv', required=True); p.add_argument('--max-expired-exceptions', type=int, default=0); a=p.parse_args()
try:
    r=json.loads(pathlib.Path(a.recert).read_text())
except Exception:
    print('F78 recert exception expiry gate failed: invalid recert json', file=sys.stderr); raise SystemExit(2)
if not isinstance(r, dict) or bool(r.get('exception_expiry_enabled', True)) is not True:
    print('F78 recert exception expiry gate failed: exception_expiry_enabled != true', file=sys.stderr); raise SystemExit(2)
e=list(csv.DictReader(pathlib.Path(a.exceptions_csv).read_text().splitlines()))
if not e or list(e[0].keys())!=['exception_id','status','days_until_expiry']:
    print('F78 recert exception expiry gate failed: invalid exceptions csv header', file=sys.stderr); raise SystemExit(2)
expired=sum(1 for x in e if (x.get('status') or '').strip().lower() in {'active','approved'} and int((x.get('days_until_expiry') or '-9999').strip())<=0)
if expired>a.max_expired_exceptions:
    print(f'F78 recert exception expiry gate failed: expired_exceptions={expired} > {a.max_expired_exceptions}', file=sys.stderr); raise SystemExit(2)

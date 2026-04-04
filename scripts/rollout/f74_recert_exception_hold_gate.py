#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--recert', required=True); p.add_argument('--holds-csv', required=True); p.add_argument('--max-hold-days', type=int, default=21); p.add_argument('--max-active-holds', type=int, default=0); a=p.parse_args()
try:
    r=json.loads(pathlib.Path(a.recert).read_text())
except Exception:
    print('F74 recert exception hold gate failed: invalid recert json', file=sys.stderr); raise SystemExit(2)
if not isinstance(r, dict) or bool(r.get('exception_hold_enforced', True)) is not True:
    print('F74 recert exception hold gate failed: exception_hold_enforced != true', file=sys.stderr); raise SystemExit(2)
h=list(csv.DictReader(pathlib.Path(a.holds_csv).read_text().splitlines()))
if not h or list(h[0].keys())!=['exception_id','hold_status','owner','days_on_hold']:
    print('F74 recert exception hold gate failed: invalid holds csv header', file=sys.stderr); raise SystemExit(2)
active=[x for x in h if (x.get('hold_status') or '').strip().lower() in {'active','on_hold'}]
expired=sum(1 for x in active if int((x.get('days_on_hold') or '9999').strip())>a.max_hold_days)
if expired>0 or len(active)>a.max_active_holds:
    print(f'F74 recert exception hold gate failed: active_holds={len(active)} expired_holds={expired}', file=sys.stderr); raise SystemExit(2)

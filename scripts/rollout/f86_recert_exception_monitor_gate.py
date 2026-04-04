#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--recert', required=True); p.add_argument('--exceptions-csv', required=True); p.add_argument('--max-stale-days', type=int, default=14); p.add_argument('--max-unmonitored-exceptions', type=int, default=0); a=p.parse_args()
try:
    r=json.loads(pathlib.Path(a.recert).read_text())
except Exception:
    print('F86 recert exception monitor gate failed: invalid recert json', file=sys.stderr); raise SystemExit(2)
if not isinstance(r, dict) or bool(r.get('exception_monitoring_enabled', True)) is not True:
    print('F86 recert exception monitor gate failed: exception_monitoring_enabled != true', file=sys.stderr); raise SystemExit(2)
e=list(csv.DictReader(pathlib.Path(a.exceptions_csv).read_text().splitlines()))
if not e or list(e[0].keys())!=['exception_id','monitor_status','days_since_last_check','owner']:
    print('F86 recert exception monitor gate failed: invalid exceptions csv header', file=sys.stderr); raise SystemExit(2)
unmonitored=[x for x in e if (x.get('monitor_status') or '').strip().lower() not in {'active','monitored'}]
stale=sum(1 for x in e if int((x.get('days_since_last_check') or '9999').strip())>a.max_stale_days)
if len(unmonitored)>a.max_unmonitored_exceptions or stale>0:
    print(f'F86 recert exception monitor gate failed: unmonitored_exceptions={len(unmonitored)} stale_exceptions={stale}', file=sys.stderr); raise SystemExit(2)

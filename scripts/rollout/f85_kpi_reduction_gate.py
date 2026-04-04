#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--kpi', required=True); p.add_argument('--reductions-csv', required=True); p.add_argument('--max-open-reductions', type=int, default=0); p.add_argument('--max-overdue-reductions', type=int, default=0); a=p.parse_args()
try:
    k=json.loads(pathlib.Path(a.kpi).read_text())
except Exception:
    print('F85 KPI reduction gate failed: invalid kpi json', file=sys.stderr); raise SystemExit(2)
if not isinstance(k, dict) or bool(k.get('kpi_reduction_tracking_enabled', True)) is not True:
    print('F85 KPI reduction gate failed: kpi_reduction_tracking_enabled != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.reductions_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['metric_id','reduction_status','days_open','owner']:
    print('F85 KPI reduction gate failed: invalid reductions csv header', file=sys.stderr); raise SystemExit(2)
open_reductions=sum(1 for x in r if (x.get('reduction_status') or '').strip().lower()!='closed')
overdue=sum(1 for x in r if (x.get('reduction_status') or '').strip().lower()!='closed' and int((x.get('days_open') or '9999').strip())>a.max_overdue_reductions)
if open_reductions>a.max_open_reductions or overdue>0:
    print(f'F85 KPI reduction gate failed: open_reductions={open_reductions} overdue_reductions={overdue} max_open={a.max_open_reductions} max_overdue_days={a.max_overdue_reductions}', file=sys.stderr); raise SystemExit(2)

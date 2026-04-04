#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--kpi', required=True); p.add_argument('--regressions-csv', required=True); p.add_argument('--max-unalerted-regressions', type=int, default=0); a=p.parse_args()
k=json.loads(pathlib.Path(a.kpi).read_text())
if not isinstance(k, dict):
    print('F69 KPI regression alert gate failed: invalid kpi json', file=sys.stderr); raise SystemExit(2)
if bool(k.get('regression_alerting_enabled', True)) is not True:
    print('F69 KPI regression alert gate failed: regression_alerting_enabled != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.regressions_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['regression_id','status','alert_status']:
    print('F69 KPI regression alert gate failed: invalid regressions csv header', file=sys.stderr); raise SystemExit(2)
u=sum(1 for x in r if (x.get('status') or '').strip().lower()=='regressed' and (x.get('alert_status') or '').strip().lower()!='alerted')
if u>a.max_unalerted_regressions:
    print(f'F69 KPI regression alert gate failed: unalerted_regressions={u} > {a.max_unalerted_regressions}', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--board', required=True); p.add_argument('--dashboard-csv', required=True); p.add_argument('--max-stale-metrics', type=int, default=0); p.add_argument('--max-days-since-refresh', type=int, default=7); a=p.parse_args()
try:
    b=json.loads(pathlib.Path(a.board).read_text())
except Exception:
    print('F76 board health dashboard gate failed: invalid board json', file=sys.stderr); raise SystemExit(2)
if not isinstance(b, dict) or bool(b.get('health_dashboard_enabled', True)) is not True:
    print('F76 board health dashboard gate failed: health_dashboard_enabled != true', file=sys.stderr); raise SystemExit(2)
d=list(csv.DictReader(pathlib.Path(a.dashboard_csv).read_text().splitlines()))
if not d or list(d[0].keys())!=['metric_id','status','days_since_refresh']:
    print('F76 board health dashboard gate failed: invalid dashboard csv header', file=sys.stderr); raise SystemExit(2)
stale=sum(1 for x in d if (x.get('status') or '').strip().lower()!='healthy' or int((x.get('days_since_refresh') or '9999').strip())>a.max_days_since_refresh)
if stale>a.max_stale_metrics:
    print(f'F76 board health dashboard gate failed: stale_metrics={stale} > {a.max_stale_metrics}', file=sys.stderr); raise SystemExit(2)

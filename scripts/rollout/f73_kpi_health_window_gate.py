#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--kpi', required=True); p.add_argument('--windows-csv', required=True); p.add_argument('--max-stale-windows', type=int, default=0); p.add_argument('--max-days-open', type=int, default=30); a=p.parse_args()
try:
    k=json.loads(pathlib.Path(a.kpi).read_text())
except Exception:
    print('F73 KPI health window gate failed: invalid kpi json', file=sys.stderr); raise SystemExit(2)
if not isinstance(k, dict) or bool(k.get('health_window_monitoring', True)) is not True:
    print('F73 KPI health window gate failed: health_window_monitoring != true', file=sys.stderr); raise SystemExit(2)
w=list(csv.DictReader(pathlib.Path(a.windows_csv).read_text().splitlines()))
if not w or list(w[0].keys())!=['window_id','status','days_since_open']:
    print('F73 KPI health window gate failed: invalid windows csv header', file=sys.stderr); raise SystemExit(2)
stale=sum(1 for x in w if (x.get('status') or '').strip().lower()!='healthy' or int((x.get('days_since_open') or '9999').strip())>a.max_days_open)
if stale>a.max_stale_windows:
    print(f'F73 KPI health window gate failed: stale_windows={stale} > {a.max_stale_windows}', file=sys.stderr); raise SystemExit(2)

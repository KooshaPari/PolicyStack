#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--kpi', required=True); p.add_argument('--anomalies-csv', required=True); p.add_argument('--max-open-anomalies', type=int, default=0); a=p.parse_args()
k=json.loads(pathlib.Path(a.kpi).read_text())
if not isinstance(k, dict):
    print('F65 KPI anomaly closure gate failed: invalid kpi json', file=sys.stderr); raise SystemExit(2)
if bool(k.get('anomaly_detection_complete', True)) is not True:
    print('F65 KPI anomaly closure gate failed: anomaly_detection_complete != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.anomalies_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['anomaly_id','status','closed_at']:
    print('F65 KPI anomaly closure gate failed: invalid anomalies csv header', file=sys.stderr); raise SystemExit(2)
o=sum(1 for x in r if (x.get('status') or '').strip().lower()!='closed')
if o>a.max_open_anomalies:
    print(f'F65 KPI anomaly closure gate failed: open_anomalies={o} > {a.max_open_anomalies}', file=sys.stderr); raise SystemExit(2)

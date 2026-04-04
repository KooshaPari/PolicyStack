#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--succession', required=True); p.add_argument('--coverage-csv', required=True); p.add_argument('--min-coverage-ratio', type=float, default=1.0); a=p.parse_args()
s=json.loads(pathlib.Path(a.succession).read_text())
if not isinstance(s, dict):
    print('F71 succession coverage gate failed: invalid succession json', file=sys.stderr); raise SystemExit(2)
if bool(s.get('coverage_tracking_enabled', True)) is not True:
    print('F71 succession coverage gate failed: coverage_tracking_enabled != true', file=sys.stderr); raise SystemExit(2)
c=list(csv.DictReader(pathlib.Path(a.coverage_csv).read_text().splitlines()))
if not c or list(c[0].keys())!=['role_id','criticality','coverage_status']:
    print('F71 succession coverage gate failed: invalid coverage csv header', file=sys.stderr); raise SystemExit(2)
q=[x for x in c if (x.get('criticality') or '').strip().lower()=='critical']
ratio=(sum(1 for x in q if (x.get('coverage_status') or '').strip().lower()=='covered')/len(q)) if q else 1.0
if ratio<a.min_coverage_ratio:
    print(f'F71 succession coverage gate failed: critical_coverage_ratio={ratio:.6f} < {a.min_coverage_ratio}', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--succession', required=True); p.add_argument('--remediation-csv', required=True); p.add_argument('--max-untracked-critical', type=int, default=0); a=p.parse_args()
s=json.loads(pathlib.Path(a.succession).read_text())
if not isinstance(s, dict):
    print('F67 succession remediation tracking gate failed: invalid succession json', file=sys.stderr); raise SystemExit(2)
if bool(s.get('tracking_enabled', True)) is not True:
    print('F67 succession remediation tracking gate failed: tracking_enabled != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.remediation_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['role_id','criticality','remediation_status']:
    print('F67 succession remediation tracking gate failed: invalid remediation csv header', file=sys.stderr); raise SystemExit(2)
u=sum(1 for x in r if (x.get('criticality') or '').strip().lower()=='critical' and (x.get('remediation_status') or '').strip().lower() not in {'tracked','closed'})
if u>a.max_untracked_critical:
    print(f'F67 succession remediation tracking gate failed: untracked_critical={u} > {a.max_untracked_critical}', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--succession', required=True); p.add_argument('--responsibility-csv', required=True); p.add_argument('--min-critical-responsibility-ratio', type=float, default=1.0); a=p.parse_args()
try:
    s=json.loads(pathlib.Path(a.succession).read_text())
except Exception:
    print('F75 succession responsibility gate failed: invalid succession json', file=sys.stderr); raise SystemExit(2)
if not isinstance(s, dict) or bool(s.get('responsibility_tracking_enabled', True)) is not True:
    print('F75 succession responsibility gate failed: responsibility_tracking_enabled != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.responsibility_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['role_id','criticality','owner','responsibility_status']:
    print('F75 succession responsibility gate failed: invalid responsibility csv header', file=sys.stderr); raise SystemExit(2)
critical=[x for x in r if (x.get('criticality') or '').strip().lower()=='critical']
covered=sum(1 for x in critical if (x.get('responsibility_status') or '').strip().lower()=='covered' and bool((x.get('owner') or '').strip()))
ratio=(covered/len(critical)) if critical else 1.0
if ratio<a.min_critical_responsibility_ratio:
    print(f'F75 succession responsibility gate failed: critical_responsibility_ratio={ratio:.6f} < {a.min_critical_responsibility_ratio}', file=sys.stderr); raise SystemExit(2)

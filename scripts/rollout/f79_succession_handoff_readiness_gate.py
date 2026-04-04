#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--succession', required=True); p.add_argument('--handoff-csv', required=True); p.add_argument('--min-readiness-ratio', type=float, default=1.0); a=p.parse_args()
try:
    s=json.loads(pathlib.Path(a.succession).read_text())
except Exception:
    print('F79 succession handoff readiness gate failed: invalid succession json', file=sys.stderr); raise SystemExit(2)
if not isinstance(s, dict) or bool(s.get('handoff_readiness_tracking_enabled', True)) is not True:
    print('F79 succession handoff readiness gate failed: handoff_readiness_tracking_enabled != true', file=sys.stderr); raise SystemExit(2)
h=list(csv.DictReader(pathlib.Path(a.handoff_csv).read_text().splitlines()))
if not h or list(h[0].keys())!=['role_id','criticality','handoff_status','handoff_owner']:
    print('F79 succession handoff readiness gate failed: invalid handoff csv header', file=sys.stderr); raise SystemExit(2)
c=[x for x in h if (x.get('criticality') or '').strip().lower()=='critical']
r=sum(1 for x in c if (x.get('handoff_status') or '').strip().lower()=='ready' and bool((x.get('handoff_owner') or '').strip()))
ratio=(r/len(c)) if c else 1.0
if ratio<a.min_readiness_ratio:
    print(f'F79 succession handoff readiness gate failed: critical_handoff_readiness_ratio={ratio:.6f} < {a.min_readiness_ratio}', file=sys.stderr); raise SystemExit(2)

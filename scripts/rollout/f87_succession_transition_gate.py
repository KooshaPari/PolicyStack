#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--succession', required=True); p.add_argument('--transitions-csv', required=True); p.add_argument('--min-transition-readiness-ratio', type=float, default=1.0); a=p.parse_args()
try:
    s=json.loads(pathlib.Path(a.succession).read_text())
except Exception:
    print('F87 succession transition gate failed: invalid succession json', file=sys.stderr); raise SystemExit(2)
if not isinstance(s, dict) or bool(s.get('transition_tracking_enabled', True)) is not True:
    print('F87 succession transition gate failed: transition_tracking_enabled != true', file=sys.stderr); raise SystemExit(2)
t=list(csv.DictReader(pathlib.Path(a.transitions_csv).read_text().splitlines()))
if not t or list(t[0].keys())!=['role_id','criticality','transition_status','transition_owner','transition_date']:
    print('F87 succession transition gate failed: invalid transitions csv header', file=sys.stderr); raise SystemExit(2)
c=[x for x in t if (x.get('criticality') or '').strip().lower()=='critical']
r=sum(1 for x in c if (x.get('transition_status') or '').strip().lower() in {'ready','planned'} and bool((x.get('transition_owner') or '').strip()))
ratio=(r/len(c)) if c else 1.0
if ratio<a.min_transition_readiness_ratio:
    print(f'F87 succession transition gate failed: critical_transition_readiness_ratio={ratio:.6f} < {a.min_transition_readiness_ratio}', file=sys.stderr); raise SystemExit(2)

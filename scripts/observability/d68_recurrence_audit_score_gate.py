#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); p.add_argument('--min-audit-score', type=float, default=1.0); a=p.parse_args()
f=pathlib.Path(a.report)
if not f.is_file():
    print(f'D68 missing report file: {f}', file=sys.stderr); raise SystemExit(2)
r=json.loads(f.read_text())
if float(r.get('recurrence_audit_score',0.0))<a.min_audit_score:
    print('D68 recurrence audit score gate failed', file=sys.stderr); raise SystemExit(2)


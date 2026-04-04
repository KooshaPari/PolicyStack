#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); p.add_argument('--min-quality-score', type=float, default=1.0); a=p.parse_args()
f=pathlib.Path(a.report)
if not f.is_file():
    print(f'D66 missing report file: {f}', file=sys.stderr); raise SystemExit(2)
r=json.loads(f.read_text())
if float(r.get('suppression_policy_quality_score',0.0))<a.min_quality_score:
    print('D66 suppression policy quality gate failed', file=sys.stderr); raise SystemExit(2)


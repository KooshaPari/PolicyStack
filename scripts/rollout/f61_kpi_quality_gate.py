#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--kpi', required=True); p.add_argument('--min-score', type=float, default=0.95); a=p.parse_args()
k=json.loads(pathlib.Path(a.kpi).read_text())
if float(k.get('quality_score',0.0))<a.min_score:
    print('F61 KPI quality gate failed', file=sys.stderr); raise SystemExit(2)

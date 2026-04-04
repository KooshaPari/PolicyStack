#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--min-score', type=float, default=0.8); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
if float(m.get('cadence_quality_score',0))<a.min_score:
    print('F60 board cadence quality below threshold', file=sys.stderr); raise SystemExit(2)

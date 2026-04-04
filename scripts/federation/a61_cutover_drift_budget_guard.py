#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-drift', type=float, default=0.02); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
if float(m.get('cutover_drift',0.0))>a.max_drift:
    print('A61 cutover drift budget exceeded', file=sys.stderr); raise SystemExit(2)

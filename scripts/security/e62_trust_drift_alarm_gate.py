#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); p.add_argument('--max-drift', type=float, default=0.03); a=p.parse_args()
r=json.loads(pathlib.Path(a.report).read_text())
if float(r.get('trust_drift',0.0))>a.max_drift:
    print('E62 trust drift alarm triggered', file=sys.stderr)
    raise SystemExit(2)

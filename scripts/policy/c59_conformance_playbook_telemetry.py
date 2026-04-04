#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--runs', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.runs).read_text())
if any(not x.get('telemetry_id') for x in r):
    print('C59 missing playbook telemetry id', file=sys.stderr); raise SystemExit(2)

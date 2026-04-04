#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--replay', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.replay).read_text())
if r.get('trust_drift_events',0)>0:
    print('E58 trust drift replay detected', file=sys.stderr)
    raise SystemExit(2)

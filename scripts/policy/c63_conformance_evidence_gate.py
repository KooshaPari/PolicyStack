#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--evidence', required=True); a=p.parse_args()
e=json.loads(pathlib.Path(a.evidence).read_text())
if int(e.get('missing_controls',0))>0:
    print('C63 conformance evidence missing controls', file=sys.stderr); raise SystemExit(2)

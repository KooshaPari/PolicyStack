#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--entries', required=True); a=p.parse_args()
e=json.loads(pathlib.Path(a.entries).read_text())
if any(x.get('fresh') is False for x in e):
    print('E57 freshness hardfail', file=sys.stderr)
    raise SystemExit(2)

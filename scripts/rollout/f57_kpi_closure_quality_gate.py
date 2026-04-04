#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--items', required=True); a=p.parse_args()
i=json.loads(pathlib.Path(a.items).read_text())
if any(not x.get('verified') for x in i):
    print('F57 unverified KPI closures', file=sys.stderr); raise SystemExit(2)

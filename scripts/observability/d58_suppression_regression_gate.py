#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--results', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.results).read_text())
if r.get('regressions',0)>0:
    print('D58 suppression regressions found', file=sys.stderr); raise SystemExit(2)

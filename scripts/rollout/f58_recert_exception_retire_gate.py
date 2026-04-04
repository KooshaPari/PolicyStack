#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--exceptions', required=True); a=p.parse_args()
e=json.loads(pathlib.Path(a.exceptions).read_text())
if any(x.get('retire_required') and not x.get('retired') for x in e):
    print('F58 pending retire-required exceptions', file=sys.stderr); raise SystemExit(2)

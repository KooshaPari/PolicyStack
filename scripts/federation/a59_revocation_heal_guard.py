#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--events', required=True); a=p.parse_args()
ev=json.loads(pathlib.Path(a.events).read_text())
loop=[e for e in ev if e.get('heal_attempts',0)>3]
if loop:
    print('A59 unsafe heal loop detected', file=sys.stderr); raise SystemExit(2)

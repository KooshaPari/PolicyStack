#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--actions', required=True); a=p.parse_args()
actions=json.loads(pathlib.Path(a.actions).read_text())
if any(not x.get('closure_certified') for x in actions):
    print('D60 uncertified recurrence actions', file=sys.stderr); raise SystemExit(2)

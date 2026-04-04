#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--evidence', required=True); a=p.parse_args()
e=json.loads(pathlib.Path(a.evidence).read_text())
if not bool(e.get('chain_complete',False)):
    print('A64 chaos evidence chain incomplete', file=sys.stderr); raise SystemExit(2)

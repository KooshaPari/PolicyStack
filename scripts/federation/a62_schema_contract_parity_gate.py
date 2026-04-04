#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.report).read_text())
if int(r.get('contract_mismatches',0))>0:
    print('A62 schema contract parity failed', file=sys.stderr); raise SystemExit(2)

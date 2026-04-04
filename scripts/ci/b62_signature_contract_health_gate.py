#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.report).read_text())
if int(r.get('signature_contract_failures',0))>0:
    print('B62 signature contract health failed', file=sys.stderr); raise SystemExit(2)

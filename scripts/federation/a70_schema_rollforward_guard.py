#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
def load(p):
    t=pathlib.Path(p).read_text()
    if str(p).lower().endswith('.csv'):
        return list(csv.DictReader(t.splitlines()))
    x=json.loads(t); return x if isinstance(x,list) else x.get('items',x.get('schemas',x.get('rollforward',[])))
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); p.add_argument('--max-blocked', type=int, default=0); a=p.parse_args()
r=load(a.report)
blocked=[x for x in r if str(x.get('rollforward_ok',x.get('status',''))).lower() in ('0','false','no','blocked','fail','failed','error')]
if len(blocked)>a.max_blocked:
    print(f'A70 schema rollforward guard failed: {len(blocked)}', file=sys.stderr); raise SystemExit(2)

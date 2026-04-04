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
    x=json.loads(t); return x if isinstance(x,list) else x.get('negotiations',[])
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); p.add_argument('--max-failures', type=int, default=0); a=p.parse_args()
r=load(a.report)
fail=[x for x in r if str(x.get('status','')).lower() not in ('ok','pass','compatible') or str(x.get('contract_ok','true')).lower() in ('0','false','no')]
if len(fail)>a.max_failures:
    print(f'A66 schema negotiation contract gate failed: {len(fail)}', file=sys.stderr); raise SystemExit(2)

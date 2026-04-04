#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
def load(p):
    t=pathlib.Path(p).read_text()
    if str(p).lower().endswith('.csv'):
        r=list(csv.DictReader(t.splitlines())); return r[0] if r else {}
    return json.loads(t)
p=argparse.ArgumentParser(); p.add_argument('--policy', required=True); p.add_argument('--expected-hash', required=True); a=p.parse_args()
x=load(a.policy)
h=str(x.get('policy_hash',x.get('hash',x.get('cutover_policy_hash','')))).strip()
if h!=a.expected_hash:
    print('A69 cutover policy hash gate failed', file=sys.stderr); raise SystemExit(2)

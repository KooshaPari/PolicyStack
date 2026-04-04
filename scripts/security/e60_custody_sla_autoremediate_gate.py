#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--breaches', required=True); a=p.parse_args()
b=json.loads(pathlib.Path(a.breaches).read_text())
if any(x.get('sla_breached') and not x.get('remediated') for x in b):
    print('E60 unresolved custody SLA breaches', file=sys.stderr)
    raise SystemExit(2)

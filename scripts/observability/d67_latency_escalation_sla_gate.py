#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-sla-breaches', type=int, default=0); a=p.parse_args()
f=pathlib.Path(a.metrics)
if not f.is_file():
    print(f'D67 missing metrics file: {f}', file=sys.stderr); raise SystemExit(2)
m=json.loads(f.read_text())
if int(m.get('latency_escalation_sla_breaches',0))>a.max_sla_breaches:
    print('D67 latency escalation SLA gate failed', file=sys.stderr); raise SystemExit(2)


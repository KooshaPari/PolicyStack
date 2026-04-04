#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}
def _pid(r): return str(r.get('id') or r.get('playbook_id') or r.get('playbook') or '?').strip()

p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--invocations-csv', required=True); p.add_argument('--max-p95-ms', type=float, default=500.0); p.add_argument('--max-failure-rate', type=float, default=0.0); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.invocations_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
b=[]
p95=float(m.get('playbook_invocation_p95_ms', m.get('invocation_p95_ms', 0.0)) or 0.0)
fr=float(m.get('playbook_invocation_failure_rate', m.get('invocation_failure_rate', 0.0)) or 0.0)
if p95>a.max_p95_ms: b.append('invocation_p95_ms')
if fr>a.max_failure_rate: b.append('invocation_failure_rate')
for r in rows:
    rp95=float(r.get('p95_ms', r.get('latency_p95_ms', 0.0)) or 0.0)
    rfr=float(r.get('failure_rate', 0.0) or 0.0)
    status=str(r.get('status','')).strip().lower()
    if _truthy(r.get('sla_breach')) or _truthy(r.get('breach')) or rp95>a.max_p95_ms or rfr>a.max_failure_rate or status in {'breach','failed','fail'}: b.append(f"playbook:{_pid(r)}")
if b: print('C71 playbook invocation SLA breach: '+','.join(sorted(set(b))), file=sys.stderr); raise SystemExit(2)

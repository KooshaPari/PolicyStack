#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)

def _truthy(v):
    return str(v).strip().lower() in {'1','true','t','yes','y'}

def _pid(r):
    return str(r.get('id') or r.get('playbook_id') or r.get('playbook') or '?').strip()

p=argparse.ArgumentParser()
p.add_argument('--playbooks', required=True)
p.add_argument('--latency-csv', required=True)
p.add_argument('--max-p95-ms', type=float, default=500.0)
p.add_argument('--max-p99-ms', type=float, default=1200.0)
p.add_argument('--max-breached-runs', type=int, default=0)
p.add_argument('--max-failed-runs', type=int, default=0)
a=p.parse_args()

playbooks=json.loads(pathlib.Path(a.playbooks).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.latency_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))

if isinstance(playbooks, dict):
    playbooks=playbooks.get('playbooks', playbooks.get('items', []))
expected=sorted({_pid(p) for p in (playbooks if isinstance(playbooks, list) else []) if _pid(p)})

p95=0.0
p99=0.0
breaches=[]
if isinstance(playbooks, dict) and playbooks:
    p95=_num(playbooks.get('playbook_latency_p95_ms', playbooks.get('p95_ms', 0.0)))
    p99=_num(playbooks.get('playbook_latency_p99_ms', playbooks.get('p99_ms', 0.0)))
if isinstance(playbooks, list):
    agg=[_num(p.get('p95_ms', p.get('playbook_p95_ms', 0.0))) for p in playbooks]
    if agg:
        p95=max(p95, max(agg))
    agg2=[_num(p.get('p99_ms', p.get('playbook_p99_ms', 0.0))) for p in playbooks]
    if agg2:
        p99=max(p99, max(agg2))

if p95>a.max_p95_ms: breaches.append('summary:p95')
if p99>a.max_p99_ms: breaches.append('summary:p99')

failed=0
breached=0
covered=set()
for row in rows:
    pid=_pid(row)
    covered.add(pid)
    if _truthy(row.get('sla_breach', row.get('breach', False))) or str(row.get('status','')).strip().lower() in {'failed','breach','timeout','error'}:
        failed+=1
        breached+=1
        breaches.append(f'failed:{pid}')
        continue
    if _num(row.get('p95_ms', row.get('latency_p95_ms', 0.0)))>a.max_p95_ms:
        breached+=1
        breaches.append(f'p95:{pid}')
    if _num(row.get('p99_ms', row.get('latency_p99_ms', 0.0)))>a.max_p99_ms:
        breached+=1
        breaches.append(f'p99:{pid}')

missing=[x for x in expected if x and x not in covered]
if missing:
    breaches.append('missing='+','.join(sorted(missing)))
if breached>a.max_breached_runs: breaches.append(f'breached_run_count={breached}')
if failed>a.max_failed_runs: breaches.append(f'failed_run_count={failed}')

if breaches:
    print('C91 playbook latency breach: '+','.join(sorted(set(breaches))), file=sys.stderr)
    raise SystemExit(2)

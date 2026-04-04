#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}
def _pid(x): return str(x.get('id') or x.get('playbook_id') or x.get('playbook') or '').strip()

p=argparse.ArgumentParser(); p.add_argument('--playbooks', required=True); p.add_argument('--coverage-csv', required=True); p.add_argument('--min-coverage', type=float, default=1.0); a=p.parse_args()
playbooks=json.loads(pathlib.Path(a.playbooks).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.coverage_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
required=sorted({_pid(x) for x in playbooks if _truthy(x.get('required',True)) and _pid(x)})
covered={str(r.get('playbook_id') or r.get('id') or '').strip() for r in rows if _truthy(r.get('covered',False))}
missing=sorted([x for x in required if x not in covered])
ratio=(len(required)-len(missing))/len(required) if required else 1.0
if missing or ratio<a.min_coverage: print('C67 playbook coverage breach: missing='+','.join(missing)+f' ratio={ratio:.6f}', file=sys.stderr); raise SystemExit(2)

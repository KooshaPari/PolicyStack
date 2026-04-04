#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)

def _ts(v):
    s=str(v or '').strip().replace('Z','+00:00')
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None

def _truthy(v):
    return str(v).strip().lower() in {'1','true','t','yes','y'}

def _oid(r):
    return str(r.get('override_id') or r.get('id') or r.get('name') or '?').strip()

p=argparse.ArgumentParser()
p.add_argument('--overrides', required=True)
p.add_argument('--override-csv', required=True)
p.add_argument('--as-of', required=True)
p.add_argument('--max-ttl-seconds', type=float, default=3600.0)
p.add_argument('--max-overdue-overrides', type=int, default=0)
p.add_argument('--max-late-completions', type=int, default=0)
a=p.parse_args()

as_of=_ts(a.as_of)
if not as_of:
    print('C90 invalid --as-of timestamp', file=sys.stderr)
    raise SystemExit(2)

try:
    overrides=json.loads(pathlib.Path(a.overrides).read_text())
except Exception:
    print('C90 invalid overrides JSON', file=sys.stderr)
    raise SystemExit(2)

if isinstance(overrides, dict):
    overrides=overrides.get('overrides', overrides.get('items', []))
if not isinstance(overrides, list):
    print('C90 overrides JSON must be a list', file=sys.stderr)
    raise SystemExit(2)

rows=sorted(list(csv.DictReader(pathlib.Path(a.override_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))

ttl_by_id={_oid(r):_num(r.get('ttl_seconds', r.get('timing_budget_seconds', 0.0)),0.0) for r in rows}

overdue=0
late=set()
for item in overrides:
    if not isinstance(item, dict) or not _truthy(item.get('active', True)):
        continue
    oid=_oid(item)
    started=_ts(item.get('started_at') or item.get('created_at') or item.get('ts'))
    if not started:
        overdue+=1
        continue
    budget=_num(item.get('ttl_seconds', item.get('timing_budget_seconds', ttl_by_id.get(oid, a.max_ttl_seconds))))
    if budget<=0:
        budget=a.max_ttl_seconds
    elapsed=(as_of-started).total_seconds()
    if elapsed>budget:
        overdue+=1
        late.add(oid)

for row in rows:
    if _truthy(row.get('active', True)) or str(row.get('active', '')).strip()=='':
        rid=_oid(row)
        budget=_num(row.get('ttl_seconds', row.get('timing_budget_seconds', ttl_by_id.get(rid, a.max_ttl_seconds))))
        if budget<=0:
            budget=a.max_ttl_seconds
        started=_ts(row.get('started_at') or row.get('created_at'))
        if started and (as_of-started).total_seconds() > budget:
            overdue+=1
            late.add(rid)

issues=[]
if overdue>a.max_overdue_overrides:
    issues.append(f'overdue_count={overdue}')
if len(late)>a.max_late_completions:
    issues.append('late='+','.join(sorted(late)))

if issues:
    print('C90 override timing budget breach: '+'; '.join(issues), file=sys.stderr)
    raise SystemExit(2)

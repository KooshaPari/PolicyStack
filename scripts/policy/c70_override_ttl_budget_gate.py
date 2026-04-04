#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}
def _ts(v):
    s=str(v or '').strip()
    if not s: return None
    s=s.replace('Z','+00:00')
    try: return dt.datetime.fromisoformat(s)
    except ValueError: return None

def _oid(r): return str(r.get('id') or r.get('override_id') or r.get('name') or '?').strip()

p=argparse.ArgumentParser(); p.add_argument('--overrides', required=True); p.add_argument('--override-csv', required=True); p.add_argument('--max-ttl-hours', type=float, default=24.0); a=p.parse_args()
ov=json.loads(pathlib.Path(a.overrides).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.override_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
max_secs=max(a.max_ttl_hours, 0.0)*3600.0
b=[]
def _breach(r):
    if not _truthy(r.get('active', True)): return False
    st=_ts(r.get('created_at') or r.get('start_at') or r.get('issued_at'))
    ex=_ts(r.get('expires_at') or r.get('expiry_at') or r.get('ttl_until'))
    if not st or not ex: return True
    return (ex-st).total_seconds()>max_secs

for x in sorted(ov, key=lambda r: json.dumps(r, sort_keys=True)):
    if _breach(x): b.append(_oid(x))
for r in rows:
    if _breach(r): b.append(_oid(r))
if b: print('C70 override ttl budget breach: '+','.join(sorted(set(b))), file=sys.stderr); raise SystemExit(2)

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

def _row_id(r): return str(r.get('id') or r.get('override_id') or r.get('name') or '?')

p=argparse.ArgumentParser(); p.add_argument('--overrides', required=True); p.add_argument('--override-csv', required=True); p.add_argument('--as-of', required=True); a=p.parse_args()
as_of=_ts(a.as_of)
if not as_of: print('C66 invalid --as-of timestamp', file=sys.stderr); raise SystemExit(2)
ov=json.loads(pathlib.Path(a.overrides).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.override_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
b=[]
for x in sorted(ov, key=lambda r: json.dumps(r, sort_keys=True)):
    if not _truthy(x.get('active',False)): continue
    ex=_ts(x.get('expires_at'))
    if not ex or ex<=as_of: b.append(_row_id(x))
for r in rows:
    if not _truthy(r.get('active',False)): continue
    ex=_ts(r.get('expires_at'))
    if not ex or ex<=as_of: b.append(_row_id(r))
if b: print('C66 override expiry enforcement breach: '+','.join(sorted(set(b))), file=sys.stderr); raise SystemExit(2)

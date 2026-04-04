#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}
def _id(r): return str(r.get('id') or r.get('item_id') or r.get('artifact') or r.get('path') or '?').strip()

p=argparse.ArgumentParser(); p.add_argument('--bundle', required=True); p.add_argument('--parity-csv', required=True); p.add_argument('--require-sha256', action='store_true'); a=p.parse_args()
bundle=json.loads(pathlib.Path(a.bundle).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.parity_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
req=sorted({str(x).strip() for x in bundle.get('required_artifacts', []) if str(x).strip()} | {str(x.get('path','')).strip() for x in bundle.get('artifacts', []) if _truthy(x.get('required', False)) and str(x.get('path','')).strip()})
seen=set(); parity_ok=set(); with_hash=set(); dup=set(); failed=[]
for r in rows:
    k=str(r.get('path') or r.get('artifact') or r.get('id') or '').strip()
    if not k: continue
    if k in seen: dup.add(k)
    seen.add(k)
    if _truthy(r.get('parity_ok', r.get('parity_pass', False))): parity_ok.add(k)
    if str(r.get('sha256','')).strip(): with_hash.add(k)
    if _truthy(r.get('mismatch')) or str(r.get('status','')).strip().lower() in {'mismatch','failed','fail','drift'}: failed.append(_id(r))
missing=sorted([x for x in req if x not in seen])
not_ok=sorted([x for x in req if x not in parity_ok])
hashless=sorted([x for x in req if a.require_sha256 and x not in with_hash])
if missing or not_ok or dup or failed or hashless:
    msg=[]
    if missing: msg.append('missing='+','.join(missing))
    if not_ok: msg.append('parity_failed='+','.join(not_ok))
    if dup: msg.append('duplicate='+','.join(sorted(dup)))
    if failed: msg.append('row_failures='+','.join(sorted(set(failed))))
    if hashless: msg.append('missing_sha256='+','.join(hashless))
    print('C72 forensic replay parity breach: '+'; '.join(msg), file=sys.stderr); raise SystemExit(2)

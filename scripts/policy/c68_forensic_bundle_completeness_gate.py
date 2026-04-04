#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}

p=argparse.ArgumentParser(); p.add_argument('--bundle', required=True); p.add_argument('--manifest-csv', required=True); a=p.parse_args()
b=json.loads(pathlib.Path(a.bundle).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.manifest_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
required=sorted({str(x).strip() for x in b.get('required_artifacts',[]) if str(x).strip()} | {str(x.get('path','')).strip() for x in b.get('artifacts',[]) if _truthy(x.get('required',False)) and str(x.get('path','')).strip()})
seen=[]; present=set(); with_hash=set(); dup=set()
for r in rows:
    pth=str(r.get('path') or r.get('artifact') or '').strip()
    if not pth: continue
    if pth in seen: dup.add(pth)
    seen.append(pth)
    if _truthy(r.get('present',False)): present.add(pth)
    if str(r.get('sha256','')).strip(): with_hash.add(pth)
missing=sorted([x for x in required if x not in present])
hashless=sorted([x for x in present if x in required and x not in with_hash])
if missing or dup or hashless:
    msg=[]
    if missing: msg.append('missing='+','.join(missing))
    if dup: msg.append('duplicate='+','.join(sorted(dup)))
    if hashless: msg.append('missing_sha256='+','.join(hashless))
    print('C68 forensic bundle completeness breach: '+'; '.join(msg), file=sys.stderr); raise SystemExit(2)

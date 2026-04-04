#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def _truthy(v):
    return str(v).strip().lower() in {'1','true','t','yes','y'}

def _oid(r):
    return str(r.get('path') or r.get('artifact') or r.get('id') or '?').strip()

def _read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print('C92 invalid bundle JSON', file=sys.stderr)
        raise SystemExit(2)

def _read_csv(path):
    rows=list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))

p=argparse.ArgumentParser()
p.add_argument('--bundle', required=True)
p.add_argument('--verification-csv', required=True)
p.add_argument('--max-verification-failures', type=int, default=0)
p.add_argument('--require-manifest', action='store_true')
p.add_argument('--require-checksums', action='store_true')
a=p.parse_args()

bundle=_read_json(a.bundle)
if not isinstance(bundle, dict):
    print('C92 bundle JSON must be an object', file=sys.stderr)
    raise SystemExit(2)

rows=_read_csv(a.verification_csv)

required=set()
if a.require_manifest and not str(bundle.get('manifest', '')).strip():
    print('C92 missing bundle manifest reference', file=sys.stderr)
    raise SystemExit(2)
for item in (bundle.get('required_artifacts') or []):
    if str(item).strip():
        required.add(str(item).strip())
for item in (bundle.get('artifacts') or []):
    if not isinstance(item, dict):
        continue
    if str(item.get('path','')).strip() and _truthy(item.get('required', True)):
        required.add(str(item['path']).strip())

expected_checksums={
    str(k).strip(): str(v).strip()
    for k,v in (bundle.get('checksums') or {}).items()
    if str(k).strip() and str(v).strip()
}

present=set()
bad=set()
dup=set()
seen=set()
missing_artifacts=[]
missing_hash=[]
for row in rows:
    rid=_oid(row)
    if rid in seen:
        dup.add(rid)
    seen.add(rid)
    if _truthy(row.get('present', True)):
        present.add(rid)
    status=str(row.get('status','')).strip().lower()
    if status in {'missing','mismatch','invalid','failed','error'}:
        bad.add(rid)
    checksum=str(row.get('sha256') or row.get('checksum') or '').strip()
    if a.require_checksums and _truthy(row.get('present', True)) and not checksum:
        bad.add(rid)
        missing_hash.append(rid)
    expected=expected_checksums.get(rid)
    if expected and checksum and checksum!=expected:
        bad.add(rid)

if required and required - present:
    missing_artifacts=sorted(required - present)
missing=[x for x in sorted(required) if x not in present]
issues=[]
if missing:
    issues.append('missing='+','.join(missing))
if dup:
    issues.append('duplicate='+','.join(sorted(dup)))
bad_sorted=sorted(set(bad))
if bad_sorted:
    issues.append('verification_failed='+','.join(bad_sorted))
if missing_hash:
    issues.append('missing_checksum='+','.join(sorted(set(missing_hash))))
if len(bad_sorted)>a.max_verification_failures:
    issues.append(f'failure_count={len(bad_sorted)}')
if missing_artifacts:
    issues.append('missing_artifacts='+','.join(missing_artifacts))

if issues:
    print('C92 forensic bundle verification breach: '+('; '.join(issues)), file=sys.stderr)
    raise SystemExit(2)

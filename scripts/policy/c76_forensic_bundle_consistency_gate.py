#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _pid(r):
    return str(r.get('id') or r.get('artifact') or r.get('path') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--bundle', required=True)
p.add_argument('--consistency-csv', required=True)
p.add_argument('--max-consistency-failures', type=int, default=0)
p.add_argument('--require-sha256', action='store_true')
a = p.parse_args()

bundle = json.loads(pathlib.Path(a.bundle).read_text())
rows = sorted(
    list(csv.DictReader(pathlib.Path(a.consistency_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

required = sorted(
    {
        str(x).strip()
        for x in bundle.get('required_artifacts', [])
        if str(x).strip()
    }
)
for artifact in bundle.get('artifacts', []):
    if _truthy(artifact.get('required', False)) and str(artifact.get('path', '')).strip():
        required.append(str(artifact['path']).strip())
required = sorted(set(required))
expected_hashes = {
    str(k).strip(): str(v).strip()
    for k, v in (bundle.get('checksums', {}) or {}).items()
    if str(k).strip() and str(v).strip()
}

seen = set()
present = set()
bad_hash = []
failures = []
duplicates = set()

for row in rows:
    key = str(row.get('path') or row.get('artifact') or '').strip()
    if not key:
        continue
    if key in seen:
        duplicates.add(key)
    seen.add(key)
    if _truthy(row.get('present', True)):
        present.add(key)
    if _truthy(row.get('mismatch', False)):
        failures.append(key)
    status = str(row.get('status', '')).strip().lower()
    if status in {'mismatch', 'inconsistent', 'bad'}:
        failures.append(key)
    hash_value = str(row.get('sha256') or row.get('checksum', '')).strip()
    if a.require_sha256 and _truthy(row.get('present', True)) and not hash_value:
        failures.append(key)
    expected = expected_hashes.get(key)
    if expected and hash_value and hash_value != expected:
        failures.append(key)
    if hash_value and expected:
        bad_hash.append(key) if hash_value != expected else None

missing = sorted([x for x in required if x not in present])
failed_unique = sorted(set(failures + bad_hash))
issues = []
if missing:
    issues.append('missing='+','.join(missing))
if duplicates:
    issues.append('duplicate='+','.join(sorted(duplicates)))
if failed_unique:
    issues.append('consistency_fail='+','.join(failed_unique))
if len(failed_unique) > a.max_consistency_failures:
    issues.append(f'failure_count={len(failed_unique)}')

if issues:
    print('C76 forensic bundle consistency breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)

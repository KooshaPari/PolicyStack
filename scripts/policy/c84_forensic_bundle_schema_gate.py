#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _oid(r):
    return str(r.get('id') or r.get('artifact') or r.get('path') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--bundle', required=True)
p.add_argument('--schema-csv', required=True)
p.add_argument('--require-schema-version', action='store_true')
p.add_argument('--require-sha256', action='store_true')
p.add_argument('--max-schema-violations', type=int, default=0)
a = p.parse_args()

try:
    bundle = json.loads(pathlib.Path(a.bundle).read_text())
except Exception:
    print('C84 invalid bundle JSON', file=sys.stderr)
    raise SystemExit(2)

if not isinstance(bundle, dict):
    print('C84 bundle JSON must be an object', file=sys.stderr)
    raise SystemExit(2)

rows = sorted(
    list(csv.DictReader(pathlib.Path(a.schema_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

required = set()
if isinstance(bundle.get('required_artifacts'), list):
    required.update({str(x).strip() for x in bundle['required_artifacts'] if str(x).strip()})
for artifact in bundle.get('artifacts', []) if isinstance(bundle.get('artifacts'), list) else []:
    if str(artifact.get('path', '')).strip() and _truthy(artifact.get('required', False)):
        required.add(str(artifact['path']).strip())

if a.require_schema_version and not str(bundle.get('schema_version', '')).strip():
    print('C84 forensic bundle schema gate failed: missing schema_version', file=sys.stderr)
    raise SystemExit(2)

seen = set()
dup = set()
violations = set()
missing_hash = []
invalid_rows = []
missing = []

for row in rows:
    key = str(row.get('path') or row.get('artifact') or row.get('id') or '').strip()
    if not key:
        continue
    if key in seen:
        dup.add(key)
    seen.add(key)
    if _truthy(a.require_sha256 and not row.get('sha256', '')):
        pass
    if a.require_sha256 and not str(row.get('sha256', '')).strip():
        missing_hash.append(key)
    if not _truthy(row.get('schema_valid', row.get('valid', False))):
        violations.add(key)
    if str(row.get('status', '')).strip().lower() in {'invalid', 'failed', 'mismatch', 'bad', 'drift'}:
        violations.add(key)
    if str(row.get('schema_errors', '')).strip():
        invalid_rows.append(key)

for key in required:
    if key not in seen:
        missing.append(key)

issues = []
if missing:
    issues.append('missing='+','.join(sorted(set(missing))))
if dup:
    issues.append('duplicate='+','.join(sorted(dup)))
if violations:
    issues.append('schema_violation='+','.join(sorted(violations)))
if missing_hash:
    issues.append('missing_sha256='+','.join(sorted(set(missing_hash))))
if invalid_rows:
    issues.append('invalid_rows='+','.join(sorted(set(invalid_rows))))
if len(violations) > a.max_schema_violations:
    issues.append(f'violation_count={len(violations)}')

if issues:
    print('C84 forensic bundle schema breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)

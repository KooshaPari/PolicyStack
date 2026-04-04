#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


def _pid(r):
    return str(r.get('id') or r.get('path') or r.get('artifact') or r.get('name') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--bundle', required=True)
p.add_argument('--fields-csv', required=True)
p.add_argument('--required-field', action='append', default=[])
p.add_argument('--max-missing-fields', type=int, default=0)
p.add_argument('--max-empty-required-fields', type=int, default=0)
a = p.parse_args()

required_fields = [x.strip() for x in a.required_field if str(x).strip()]

try:
    bundle = json.loads(pathlib.Path(a.bundle).read_text())
except Exception:
    print('C88 invalid bundle JSON', file=sys.stderr)
    raise SystemExit(2)

if not isinstance(bundle, dict):
    print('C88 bundle JSON must be an object', file=sys.stderr)
    raise SystemExit(2)

required = set(required_fields)
for field in (bundle.get('required_fields') or []):
    if str(field).strip():
        required.add(str(field).strip())

artifact_fields = {}
for artifact in bundle.get('artifacts', []) if isinstance(bundle.get('artifacts'), list) else []:
    if not isinstance(artifact, dict):
        continue
    key = str(artifact.get('id') or artifact.get('path') or artifact.get('artifact') or '').strip()
    if not key:
        continue
    fields = artifact.get('required_fields')
    if isinstance(fields, list):
        req = {str(x).strip() for x in fields if str(x).strip()}
        if req:
            artifact_fields[key] = req

rows = _read_csv(a.fields_csv)
if not rows:
    print('C88 missing artifact field rows', file=sys.stderr)
    raise SystemExit(2)

missing_field_count = 0
missing = []
empty_required = []
for row in rows:
    key = _pid(row)
    if not key:
        continue
    required_for_artifact = set(required)
    required_for_artifact.update(artifact_fields.get(key, set()))
    for field in required_for_artifact:
        if field not in row:
            missing.append(f'{key}:{field}')
        elif not str(row.get(field, '')).strip():
            empty_required.append(f'{key}:{field}')

issues = []
if missing:
    issues.append('missing='+','.join(sorted(set(missing))))
if len(empty_required) > a.max_empty_required_fields:
    issues.append(f'empty_required_fields={len(empty_required)}')
if len(missing) > a.max_missing_fields:
    issues.append(f'missing_fields_count={len(missing)}')

if issues:
    print('C88 forensic bundle missing fields breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _oid(r):
    return str(r.get('artifact') or r.get('path') or r.get('id') or '?').strip()


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f'{label} invalid JSON', file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


p = argparse.ArgumentParser()
p.add_argument('--bundle', required=True)
p.add_argument('--coherence-csv', required=True)
p.add_argument('--max-coherence-violations', type=int, default=0)
p.add_argument('--max-missing-artifacts', type=int, default=0)
p.add_argument('--max-schema-mismatches', type=int, default=0)
p.add_argument('--require-checksums', action='store_true')
a = p.parse_args()

bundle = _read_json(a.bundle, 'C96 bundle')
rows = _read_csv(a.coherence_csv)

if not isinstance(bundle, dict):
    print('C96 bundle JSON must be an object', file=sys.stderr)
    raise SystemExit(2)

required = set()
for item in bundle.get('required_artifacts', []) if isinstance(bundle.get('required_artifacts'), list) else []:
    if str(item).strip():
        required.add(str(item).strip())
for artifact in bundle.get('artifacts', []) if isinstance(bundle.get('artifacts'), list) else []:
    if not isinstance(artifact, dict):
        continue
    if _truthy(artifact.get('required', True)):
        path = str(artifact.get('path', '')).strip()
        if path:
            required.add(path)

checksums = {
    str(k).strip(): str(v).strip()
    for k, v in (bundle.get('checksums', {}) or {}).items()
    if str(k).strip()
}

seen = set()
duplicates = set()
coherent = set()
violations = []
missing_hash = []
schema_mismatch = []

for row in rows:
    oid = _oid(row)
    if not oid:
        continue
    if oid in seen:
        duplicates.add(oid)
    seen.add(oid)

    state = str(row.get('state', '')).strip().lower()
    if state == 'coherent':
        coherent.add(oid)
    if str(row.get('status', '')).strip().lower() in {'incoherent', 'bad', 'mismatch', 'missing'}:
        violations.append(oid)
    if a.require_checksums:
        if not str(row.get('sha256', row.get('checksum', '')).strip()):
            missing_hash.append(oid)
    expected = checksums.get(oid)
    actual = str(row.get('sha256', row.get('checksum', '')).strip())
    if expected and actual and expected != actual:
        schema_mismatch.append(oid)
    depends = row.get('depends_on')
    if depends:
        for dep in str(depends).split(','):
            dep_id = dep.strip()
            if dep_id and dep_id not in required:
                violations.append(f'{oid}:{dep_id}')

missing = sorted(required - seen)
missing_violations = len(missing)
coherence_violations = len(set(violations + schema_mismatch + missing_hash))
issues = []
if missing:
    issues.append('missing=' + ','.join(missing))
if duplicates:
    issues.append('duplicate=' + ','.join(sorted(duplicates)))
if coherence_violations > a.max_coherence_violations:
    issues.append(f'coherence_violations={coherence_violations}')
if missing_violations > a.max_missing_artifacts:
    issues.append(f'missing_artifacts={missing_violations}')
if len(schema_mismatch) > a.max_schema_mismatches:
    issues.append(f'schema_mismatch={len(schema_mismatch)}')
if missing_hash and len(missing_hash) > 0:
    issues.append('missing_checksum=' + ','.join(sorted(set(missing_hash))))
if len(coherent) == 0 and required:
    issues.append('no_coherent_artifacts')

if issues:
    print('C96 forensic bundle coherence breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)

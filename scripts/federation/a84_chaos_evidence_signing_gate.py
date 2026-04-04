#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
def load(path):
    raw=pathlib.Path(path).read_text()
    if str(path).lower().endswith('.csv'):
        rows=list(csv.DictReader(raw.splitlines())); return rows[0] if rows else {}
    return json.loads(raw)
parser=argparse.ArgumentParser()
parser.add_argument('--evidence', required=True)
parser.add_argument('--min-signatures', type=int, default=2)
parser.add_argument('--max-missing-signatures', type=int, default=0)
args=parser.parse_args()
e=load(args.evidence)
required=int(float(e.get('required_signatures', e.get('expected_signatures', args.min_signatures))))
observed=int(float(e.get('observed_signatures', e.get('signature_count', 0))))
missing=int(float(e.get('missing_signatures', max(required - observed, 0))))
invalid=int(float(e.get('invalid_signatures', 0)))
if required < args.min_signatures or observed < required or missing > args.max_missing_signatures or invalid > 0:
    print('A84 chaos evidence signing gate failed', file=sys.stderr)
    raise SystemExit(2)

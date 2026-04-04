#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--retention', required=True); p.add_argument('--min-retention-days', type=int, default=1); a=p.parse_args()
r=json.loads(pathlib.Path(a.retention).read_text())
min_ok=int(float(r.get('retention_days', 0)))>=a.min_retention_days
immutable=bool(r.get('immutable', r.get('retention_immutable', r.get('is_immutable', False))))
if not min_ok or not immutable:
    print('A76 chaos retention immutability gate failed', file=sys.stderr); raise SystemExit(2)

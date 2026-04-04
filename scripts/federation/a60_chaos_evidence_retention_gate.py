#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--bundle', required=True); a=p.parse_args()
b=json.loads(pathlib.Path(a.bundle).read_text())
missing=[k for k in ('run_id','scenario','sha256','retention_days') if k not in b]
if missing:
    print('A60 missing evidence fields: '+','.join(missing), file=sys.stderr); raise SystemExit(2)

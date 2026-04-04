#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--archive', required=True); a=p.parse_args()
ae=json.loads(pathlib.Path(a.archive).read_text())
if any(x.get('tampered') for x in ae):
    print('E59 lineage tamper detected', file=sys.stderr)
    raise SystemExit(2)

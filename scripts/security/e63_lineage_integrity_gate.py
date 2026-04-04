#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--lineage', required=True); a=p.parse_args()
l=json.loads(pathlib.Path(a.lineage).read_text())
if int(l.get('integrity_violations',0))>0:
    print('E63 lineage integrity violation', file=sys.stderr)
    raise SystemExit(2)

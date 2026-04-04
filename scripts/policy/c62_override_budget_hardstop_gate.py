#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--overrides', required=True); p.add_argument('--max-active', type=int, default=0); a=p.parse_args()
o=json.loads(pathlib.Path(a.overrides).read_text())
if len([x for x in o if x.get('active',False)])>a.max_active:
    print('C62 override budget hardstop breach', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--recert', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.recert).read_text())
if int(r.get('stale_exceptions',0))>0:
    print('F62 recert retirement gate failed', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--succession', required=True); a=p.parse_args()
s=json.loads(pathlib.Path(a.succession).read_text())
if int(s.get('critical_uncovered',0))>0:
    print('F63 succession health gate failed', file=sys.stderr); raise SystemExit(2)

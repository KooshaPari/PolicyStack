#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--scores', required=True); p.add_argument('--min-score', type=float, default=0.8); a=p.parse_args()
s=json.loads(pathlib.Path(a.scores).read_text())
if float(s.get('effective_score',0))<a.min_score:
    print('B60 CAPA score below minimum', file=sys.stderr); raise SystemExit(2)

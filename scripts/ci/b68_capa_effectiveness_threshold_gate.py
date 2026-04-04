#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--scores', required=True); p.add_argument('--score-key', default='effectiveness_score'); p.add_argument('--min-score', type=float, default=0.8); a=p.parse_args()
s=json.loads(pathlib.Path(a.scores).read_text())
if float(s.get(a.score_key,0))<a.min_score:
    print('B68 CAPA effectiveness threshold gate failed', file=sys.stderr); raise SystemExit(2)

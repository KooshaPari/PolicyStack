#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max_fail', type=int, default=0); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
if int(m.get('invariant_failures',0))>a.max_fail:
    print('A57 invariant SLO breach', file=sys.stderr); raise SystemExit(2)

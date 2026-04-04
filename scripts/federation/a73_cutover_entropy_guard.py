#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--entropy', required=True); p.add_argument('--min-entropy', type=float, default=0.8); a=p.parse_args()
e=json.loads(pathlib.Path(a.entropy).read_text())
value=float(e.get('entropy', e.get('cutover_entropy', 0.0)))
if value<a.min_entropy:
    print('A73 cutover entropy guard failed', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--health', required=True); p.add_argument('--min-heal-rate', type=float, default=0.99); a=p.parse_args()
h=json.loads(pathlib.Path(a.health).read_text())
if float(h.get('autoheal_rate',1.0))<a.min_heal_rate:
    print('A63 revocation autoheal regression', file=sys.stderr); raise SystemExit(2)

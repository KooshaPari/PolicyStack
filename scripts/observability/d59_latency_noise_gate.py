#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-dup', type=int, default=10); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
if int(m.get('duplicate_escalations',0))>a.max_dup:
    print('D59 escalation noise too high', file=sys.stderr); raise SystemExit(2)

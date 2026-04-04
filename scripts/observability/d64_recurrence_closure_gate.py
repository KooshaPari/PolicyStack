#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-recurrence', type=int, default=0); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
if int(m.get('open_recurrence',0))>a.max_recurrence:
    print('D64 recurrence closure failed', file=sys.stderr); raise SystemExit(2)

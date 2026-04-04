#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-loop-ms', type=float, default=500.0); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
if float(m.get('replay_loop_p95_ms',0.0))>a.max_loop_ms:
    print('C61 replay governor SLO breach', file=sys.stderr); raise SystemExit(2)

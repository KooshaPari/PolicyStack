#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--latency', required=True); p.add_argument('--max-p95-ms', type=float, default=1500.0); a=p.parse_args()
l=json.loads(pathlib.Path(a.latency).read_text())
if float(l.get('override_p95_ms',0.0))>a.max_p95_ms:
    print('D61 override latency guard failed', file=sys.stderr); raise SystemExit(2)

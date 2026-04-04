#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--latency', required=True); p.add_argument('--max-p95-ms', type=float, default=100.0); p.add_argument('--max-p99-ms', type=float, default=300.0)
a=p.parse_args()
l=json.loads(pathlib.Path(a.latency).read_text())
p95=float(l.get('p95_ms', l.get('revocation_p95_ms', 0.0))); p99=float(l.get('p99_ms', l.get('revocation_p99_ms', 0.0)))
if p95>a.max_p95_ms or p99>a.max_p99_ms:
    print('A75 revocation latency budget gate failed', file=sys.stderr); raise SystemExit(2)

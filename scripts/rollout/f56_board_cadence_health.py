#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--min-health', type=float, default=0.8); args=p.parse_args()
    m=json.loads(pathlib.Path(args.metrics).read_text())
    h=float(m.get('health_score',0.0))
    if h < args.min_health:
        print(f'F56 cadence health low: {h}', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

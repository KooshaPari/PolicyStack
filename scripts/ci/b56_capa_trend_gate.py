#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--trend', required=True)
    p.add_argument('--max-regression', type=float, default=0.05)
    args=p.parse_args()
    t=json.loads(pathlib.Path(args.trend).read_text())
    if float(t.get('regression_rate',0.0)) > args.max_regression:
        print('B56 CAPA trend gate failed', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

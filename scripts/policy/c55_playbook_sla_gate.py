#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--runs', required=True)
    args=p.parse_args()
    runs=json.loads(pathlib.Path(args.runs).read_text())
    bad=[r for r in runs if r.get('elapsed_minutes',999)>r.get('sla_minutes',60)]
    if bad:
        print(f'C55 SLA breaches: {len(bad)}', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

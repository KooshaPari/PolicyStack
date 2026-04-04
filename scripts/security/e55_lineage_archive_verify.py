#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--archive', required=True); args=p.parse_args()
    a=json.loads(pathlib.Path(args.archive).read_text())
    bad=[x for x in a if not x.get('hash') or not x.get('source')]
    if bad:
        print(f'E55 invalid lineage entries: {len(bad)}', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

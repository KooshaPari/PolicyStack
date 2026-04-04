#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--csv', required=True); args=p.parse_args()
    rows=list(csv.DictReader(pathlib.Path(args.csv).open()))
    bad=[r for r in rows if r.get('backup_owner','')=='']
    if bad:
        print(f'F55 missing backup owners: {len(bad)}', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

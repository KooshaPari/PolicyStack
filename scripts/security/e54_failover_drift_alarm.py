#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--signals', required=True)
    args=p.parse_args()
    s=json.loads(pathlib.Path(args.signals).read_text())
    if any(x.get('trust_drift') for x in s):
        print('E54 trust drift detected', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

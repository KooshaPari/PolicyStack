#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--results', required=True)
    args=p.parse_args()
    r=json.loads(pathlib.Path(args.results).read_text())
    regress=[x for x in r if x.get('regressed')]
    if regress:
        print(f'D54 regressions: {len(regress)}', file=sys.stderr)
        return 2
    return 0
if __name__=='__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', required=True)
    args = p.parse_args()
    b = json.loads(pathlib.Path(args.bundle).read_text())
    chain = b.get('attestation_chain', [])
    if not chain:
        print('A56 missing attestation chain', file=sys.stderr)
        return 2
    for i, x in enumerate(chain):
        if i and x.get('parent') != chain[i-1].get('id'):
            print('A56 broken attestation chain', file=sys.stderr)
            return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

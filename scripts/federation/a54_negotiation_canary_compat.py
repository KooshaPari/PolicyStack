#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--matrix', required=True)
    p.add_argument('--pair', required=True)
    args = p.parse_args()
    m = json.loads(pathlib.Path(args.matrix).read_text())
    if args.pair not in set(m.get('canary_allowed_pairs', [])):
        print(f'A54 blocked pair: {args.pair}', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--events', required=True)
    p.add_argument('--max-rollback-depth', type=int, default=3)
    args = p.parse_args()
    ev = json.loads(pathlib.Path(args.events).read_text())
    bad = [e for e in ev if e.get('rollback_depth', 0) > args.max_rollback_depth]
    if bad:
        print(f'A55 rollback depth violations: {len(bad)}', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

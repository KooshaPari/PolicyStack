#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--overrides", required=True)
    args = p.parse_args()
    data = json.loads(pathlib.Path(args.overrides).read_text())
    bad = [o for o in data if not o.get("expires_at")]
    if bad:
        print(f"D53 hard-stop: {len(bad)} non-expiring overrides", file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

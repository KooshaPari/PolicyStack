#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    args = p.parse_args()
    m = json.loads(pathlib.Path(args.manifest).read_text())
    required = ['signature_version','payload_hash','issuer','issued_at']
    missing = [k for k in required if k not in m]
    if missing:
        print('B54 missing: ' + ','.join(missing), file=sys.stderr)
        return 2
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

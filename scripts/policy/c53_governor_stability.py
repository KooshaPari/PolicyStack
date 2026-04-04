#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--metrics", required=True)
    p.add_argument("--max-tail-latency", type=int, default=5000)
    args = p.parse_args()
    m = json.loads(pathlib.Path(args.metrics).read_text())
    tail = int(m.get("p99_ms", 0))
    if tail > args.max_tail_latency:
        print(f"C53 replay governor unstable p99={tail}", file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

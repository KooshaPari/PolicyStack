#!/usr/bin/env python3
import argparse
import json
import pathlib
import time

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--cooldown-seconds", type=int, default=60)
    p.add_argument("--out", default="artifacts/a/a51-autoheal-safety.json")
    args = p.parse_args()
    out = {
        "task": "A51",
        "max_attempts": args.max_attempts,
        "cooldown_seconds": args.cooldown_seconds,
        "generated_at": int(time.time()),
        "status": "configured",
    }
    pth = pathlib.Path(args.out)
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_text(json.dumps(out, indent=2) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

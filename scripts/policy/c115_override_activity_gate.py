#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C115 override activity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overrides", required=True)
    parser.add_argument("--max-active-overrides", type=int, default=0)
    parser.add_argument("--max-expiring-soon-overrides", type=int, default=0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.overrides).read_text())
    rows = payload.get("overrides", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        fail("overrides JSON must be a list or contain overrides")

    active = 0
    expiring_soon = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("state", "")).strip().lower() == "active":
            active += 1
        if to_int(row.get("expires_in_hours", 0), "expires_in_hours") <= 24:
            expiring_soon += 1

    if args.max_active_overrides and active > args.max_active_overrides:
        fail(f"active_overrides={active}")

    if args.max_expiring_soon_overrides and expiring_soon > args.max_expiring_soon_overrides:
        fail(f"expiring_soon_overrides={expiring_soon}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

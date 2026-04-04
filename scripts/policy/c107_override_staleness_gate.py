#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C107 override staleness gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_number(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid number in {field}: {v!r}")


def parse_ts(value, field):
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        fail(f"invalid timestamp in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overrides", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--max-stale-hours", type=float, default=24.0)
    parser.add_argument("--max-stale-count", type=int, default=0)
    args = parser.parse_args()

    as_of = parse_ts(args.as_of, "as-of")
    payload = json.loads(pathlib.Path(args.overrides).read_text())
    if isinstance(payload, dict):
        rows = payload.get("overrides", [])
    else:
        rows = payload

    if not isinstance(rows, list):
        fail("overrides JSON must be list or contain overrides")

    stale = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("active", "true")).lower() in {"false", "0", "no"}:
            continue
        updated_at = parse_ts(row.get("updated_at", as_of.isoformat()), "updated_at")
        age_hours = (as_of - updated_at).total_seconds() / 3600.0
        ttl = row.get("ttl_hours", args.max_stale_hours)
        ttl_hours = to_number(ttl, "ttl_hours")
        if age_hours > ttl_hours:
            stale += 1

    if stale > args.max_stale_count:
        fail(f"stale_overrides={stale}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C109 forensic bundle density gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def to_bool(v, field):
    if isinstance(v, bool):
        return v
    if str(v).strip().lower() in {"1", "true", "yes", "y"}:
        return True
    if str(v).strip().lower() in {"0", "false", "no", "n"}:
        return False
    fail(f"invalid bool in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--max-empty-bundles", type=int, default=0)
    parser.add_argument("--max-high-density-count", type=int, default=0)
    parser.add_argument("--max-density-threshold", type=float, default=0.75)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.snapshot).read_text())
    if not isinstance(payload, dict):
        fail("snapshot must be JSON object")

    bundles = payload.get("bundles", [])
    if not isinstance(bundles, list):
        fail("snapshot.bundles must be a list")

    empty_bundles = 0
    high_density_count = 0
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        if to_bool(bundle.get("is_empty", False), "is_empty"):
            empty_bundles += 1
            continue

        density = bundle.get("density", 0.0)
        try:
            density = float(density)
        except (TypeError, ValueError):
            fail(f"invalid density in bundle: {density!r}")

        if density > args.max_density_threshold:
            high_density_count += 1

    if empty_bundles > args.max_empty_bundles:
        fail(f"empty_bundles={empty_bundles}")

    if high_density_count > args.max_high_density_count:
        fail(f"high_density_bundles={high_density_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

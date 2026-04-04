#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def parse_float(value: object, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric {label}: {value!r}") from exc


def parse_stats(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse JSON stats from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"stats payload must be a JSON object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", required=True)
    parser.add_argument("--entropy-key", default="attestation_signature_entropy")
    parser.add_argument("--min-entropy", type=float, default=0.0)
    parser.add_argument("--max-entropy", type=float, default=None)
    args = parser.parse_args()

    try:
        stats = parse_stats(pathlib.Path(args.stats))
        entropy = parse_float(
            stats.get(args.entropy_key),
            f"missing/invalid value for {args.entropy_key}",
        )
    except (OSError, ValueError) as exc:
        print(f"B91 attestation signature entropy gate failed: {exc}", file=sys.stderr)
        return 2

    if args.max_entropy is not None and entropy > args.max_entropy:
        print(
            "B91 attestation signature entropy gate failed: "
            f"entropy={entropy:.6f} > max_entropy={args.max_entropy}",
            file=sys.stderr,
        )
        return 2
    if entropy < args.min_entropy:
        print(
            "B91 attestation signature entropy gate failed: "
            f"entropy={entropy:.6f} < min_entropy={args.min_entropy}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

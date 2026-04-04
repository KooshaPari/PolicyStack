#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E101 attestation chain completeness gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_rows(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(path.read_text().splitlines()))
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        for key in ("attestations", "items", "records", "entries"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return rows
        fail("attestations payload must include attestations/items/records/entries")
    if not isinstance(payload, list):
        fail("attestations payload must be list or object with attestations/items/records/entries")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--chain-col", default="chain_id")
    parser.add_argument("--max-missing-chain", type=int, default=0)
    args = parser.parse_args()

    rows = _load_rows(pathlib.Path(args.attestations))
    missing = sum(1 for row in rows if not str(row.get(args.chain_col, "")).strip())

    if missing > args.max_missing_chain:
        fail(f"missing_chain_id={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

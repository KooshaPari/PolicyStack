#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def load(path):
    raw = pathlib.Path(path).read_text()
    if str(path).lower().endswith(".csv"):
        rows = list(csv.DictReader(raw.splitlines()))
        return rows[0] if rows else {}
    return json.loads(raw)


def to_int(v):
    return int(float(v)) if str(v).strip() else 0


p = argparse.ArgumentParser()
p.add_argument("--evidence", required=True)
p.add_argument("--max-tamper-events", type=int, default=0)
p.add_argument("--max-hash-mismatches", type=int, default=0)
args = p.parse_args()

e = load(args.evidence)
tamper = to_int(e.get("tamper_events", e.get("tamper_count", 0)))
hash_mismatch = to_int(e.get("hash_mismatches", e.get("evidence_hash_mismatches", 0)))
signature_ok = bool(e.get("signatures_valid", e.get("signature_chain_valid", True)))

if tamper > args.max_tamper_events or hash_mismatch > args.max_hash_mismatches or not signature_ok:
    print("A88 chaos evidence tamper gate failed", file=sys.stderr)
    raise SystemExit(2)


#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


p = argparse.ArgumentParser()
p.add_argument("--stats", required=True)
p.add_argument("--covered-key", default="attestation_signature_covered")
p.add_argument("--total-key", default="attestation_signature_total")
p.add_argument("--min-coverage-ratio", type=float, default=1.0)
a = p.parse_args()

stats = json.loads(pathlib.Path(a.stats).read_text())
covered = float(stats.get(a.covered_key, 0.0) or 0.0)
total = float(stats.get(a.total_key, 0.0) or 0.0)
coverage_ratio = (covered / total) if total > 0 else 1.0

if coverage_ratio < a.min_coverage_ratio:
    print("B87 attestation signature coverage gate failed", file=sys.stderr)
    raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)


def _oid(r):
    return str(r.get("id") or r.get("artifact_id") or r.get("artifact") or r.get("path") or "?").strip()


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f"C100 {label} invalid JSON", file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    try:
        rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    except Exception:
        print("C100 bundle gap CSV invalid", file=sys.stderr)
        raise SystemExit(2)
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


def _fail(message):
    print(f"C100 forensic bundle gap breach: {message}", file=sys.stderr)
    raise SystemExit(2)


p = argparse.ArgumentParser()
p.add_argument("--bundle", required=True)
p.add_argument("--gap-csv", required=True)
p.add_argument("--max-total-gaps", type=int, default=0)
p.add_argument("--max-open-gaps", type=int, default=0)
p.add_argument("--max-gap-severity", type=float, default=1.0)
p.add_argument("--max-missing-required-artifacts", type=int, default=0)
a = p.parse_args()

bundle = _read_json(a.bundle, "bundle")
rows = _read_csv(a.gap_csv)

if not isinstance(bundle, dict):
    _fail("bundle JSON must be an object")

required = set()
for item in bundle.get("required_artifacts", []):
    item_name = str(item).strip()
    if item_name:
        required.add(item_name)
for artifact in bundle.get("artifacts", []):
    if not isinstance(artifact, dict):
        continue
    path = str(artifact.get("path", "")).strip()
    if path and _truthy(artifact.get("required", True)):
        required.add(path)

seen = set()
open_count = 0
total_gaps = 0
severity_total = 0.0
severity_count = 0
missing = set()

for row in rows:
    oid = _oid(row)
    seen.add(oid)
    status = str(row.get("status", "")).strip().lower()
    is_gap = _truthy(row.get("gap", row.get("is_gap", False)))
    if is_gap:
        total_gaps += 1
        gap_size = _num(row.get("gap_size", row.get("missing_ratio", 0.0)))
        severity_total += gap_size
        severity_count += 1
    if status in {"open", "pending", "unresolved"} or _truthy(row.get("open", False)):
        open_count += 1
        if not _truthy(row.get("resolved", row.get("closed", False))):

for artifact in sorted(required):
    if artifact not in seen:
        missing.add(artifact)

max_severity = (severity_total / severity_count) if severity_count else 0.0
issues = []
if total_gaps > a.max_total_gaps:
    issues.append(f"total_gaps={total_gaps}")
if open_count > a.max_open_gaps:
    issues.append(f"open_gaps={open_count}")
if max_severity > a.max_gap_severity:
    issues.append(f"avg_gap_severity={max_severity:.4f}")
if len(missing) > a.max_missing_required_artifacts:
    issues.append("missing_required=" + ",".join(sorted(missing)))
if issues:
    _fail("; ".join(issues))

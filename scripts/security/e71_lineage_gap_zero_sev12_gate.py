#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def _rows(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(path.open()))
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("vulnerabilities"), list):
            return data["vulnerabilities"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("lineage"), list):
            return data["lineage"]
    return []

def _sev12(r: dict) -> bool:
    sev = str(r.get("severity") or r.get("sev") or r.get("priority") or "").strip().lower()
    return sev in {"sev1", "sev2", "s1", "s2", "1", "2", "critical", "high"}

def _has_gap(r: dict) -> bool:
    if bool(r.get("lineage_gap") or r.get("gap")):
        return True
    lineage = r.get("lineage_id") or r.get("lineage_ref") or r.get("trace_id")
    source = r.get("source_commit") or r.get("artifact_digest") or r.get("sbom_ref")
    return not (lineage and source)

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lineage", required=True)
    p.add_argument("--max-sev12-gaps", type=int, default=0)
    a = p.parse_args()
    bad = [str(r.get("vuln_id") or r.get("cve") or r.get("id") or "") for r in _rows(pathlib.Path(a.lineage)) if _sev12(r) and _has_gap(r)]
    if len(bad) > a.max_sev12_gaps:
        bad.sort()
        print(f"E71 lineage gap zero sev1/2 breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

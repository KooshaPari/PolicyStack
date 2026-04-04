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
    return []

def _missing_trace(r: dict) -> bool:
    vuln = r.get("vuln_id") or r.get("cve") or r.get("id")
    lineage = r.get("lineage_id") or r.get("lineage_ref")
    source = r.get("source_commit") or r.get("artifact_digest") or r.get("sbom_ref")
    return not (vuln and lineage and source)

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lineage", required=True)
    a = p.parse_args()
    missing = [str(r.get("vuln_id") or r.get("cve") or r.get("id") or "") for r in _rows(pathlib.Path(a.lineage)) if _missing_trace(r)]
    if missing:
        missing.sort()
        print(f"E67 vuln lineage traceability breach: {len(missing)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

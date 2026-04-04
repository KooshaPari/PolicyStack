#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def _load_rows(path: pathlib.Path) -> tuple[list[dict], str | None]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.open())), None
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"E75 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("lineage", "items", "records", "chain", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E75 invalid input: expected list or dict with lineage/items/records/chain/entries"


def _truthy(v: object) -> bool:
    return bool(v is not None and str(v).strip() and str(v).strip().lower() not in {"false", "0", "no", "none", "null"})


def _missing_poc(row: dict) -> bool:
    proof = row.get("proof_of_custody") or row.get("custody_proof") or row.get("poc") or row.get("lineage_proof")
    if not _truthy(proof):
        return True
    if not (row.get("artifact_id") or row.get("entity_id") or row.get("object_id") or row.get("subject_id")):
        return True
    if not (row.get("lineage_id") or row.get("lineage_ref") or row.get("trace_id")):
        return True
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lineage", required=True)
    p.add_argument("--max-proof-gaps", type=int, default=0)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.lineage))
    if err:
        print(err, file=sys.stderr)
        return 2
    bad = [str(r.get("id") or r.get("lineage_id") or r.get("artifact_id") or "") for r in rows if _missing_poc(r)]
    if len(bad) > args.max_proof_gaps:
        bad.sort()
        print(f"E75 lineage proof-of-custody breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

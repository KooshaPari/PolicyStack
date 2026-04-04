#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E103 lineage orphan link gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_rows(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        for key in ("lineage", "items", "records", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
        fail("lineage payload must include lineage/items/records/entries")
    if not isinstance(data, list):
        fail("lineage payload must be list or object with lineage/items/records/entries")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--id-col", default="id")
    parser.add_argument("--parent-col", default="parent_id")
    parser.add_argument("--max-orphans", type=int, default=0)
    args = parser.parse_args()

    rows = _load_rows(pathlib.Path(args.lineage))
    known_ids = {str(row.get(args.id_col, "")) for row in rows if isinstance(row, dict)}
    known_ids.discard("")

    orphans = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        parent = str(row.get(args.parent_col, "")).strip()
        if not parent:
            continue
        if parent not in known_ids:
            orphans += 1

    if orphans > args.max_orphans:
        fail(f"orphaned_parent_count={orphans}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

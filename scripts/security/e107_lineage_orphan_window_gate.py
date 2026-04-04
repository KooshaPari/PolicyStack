#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E107 lineage orphan window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_rows(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        for key in ("lineage", "items", "records", "entries", "windows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
        fail("lineage payload must include lineage/items/records/entries/windows")
    if not isinstance(data, list):
        fail("lineage payload must be list or object with lineage/items/records/entries/windows")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--window-col", default="window_id")
    parser.add_argument("--max-orphans", type=int, default=0)
    args = parser.parse_args()

    rows = _load_rows(pathlib.Path(args.lineage))
    orphans = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("orphan", "")).strip().lower() in {"1", "true", "yes", "orphaned"}:
            orphans += 1
        elif str(row.get(args.window_col, "")).strip() == "":
            orphans += 1
    if orphans > args.max_orphans:
        fail(f"orphaned_windows={orphans}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

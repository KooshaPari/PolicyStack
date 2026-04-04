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
        return [], f"E84 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("custody", "chains", "items", "records", "lineage"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E84 invalid input: expected list or dict with custody/chains/items/records/lineage"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--custody", required=True)
    p.add_argument("--max-broken-links", type=int, default=0)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.custody))
    if err:
        print(err, file=sys.stderr)
        return 2
    ids = {_pick(r, ("chain_id", "custody_chain_id", "id")) for r in rows if _pick(r, ("chain_id", "custody_chain_id", "id"))}
    broken = sorted(
        {
            _pick(r, ("chain_id", "custody_chain_id", "id"))
            for r in rows
            if (parent := _pick(r, ("parent_chain_id", "parent_id", "prev_chain_id", "previous_chain_id")))
            and parent not in ids
        }
    )
    if len(broken) > args.max_broken_links:
        print(f"E84 custody chain broken link breach: {len(broken)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

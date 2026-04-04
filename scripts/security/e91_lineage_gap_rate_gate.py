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
        return [], f"E91 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("lineage", "items", "records", "chains", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E91 invalid input: expected list or dict with lineage/items/records/chains/entries",
    )


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _is_gap(row: dict) -> bool:
    if str(row.get("status", "")).strip().lower() in {
        "missing", "gap", "incomplete", "broken"
    }:
        return True
    if bool(
        row.get("gap")
        or row.get("lineage_gap")
        or row.get("break")
        or row.get("missing_parent")
    ):
        return True

    lineage_id = _pick(
        row,
        ("lineage_id", "lineage_ref", "trace_id", "artifact_id"),
    )
    source = _pick(row, ("source_commit", "source", "artifact_digest", "parent_digest"))
    return not bool(lineage_id and source)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--max-gap-rate", type=float, default=0.0)
    parser.add_argument("--max-gap-count", type=int, default=0)
    parser.add_argument("--min-samples", type=int, default=1)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.lineage))
    if err:
        print(err, file=sys.stderr)
        return 2

    total = len(rows)
    if total < args.min_samples:
        print(
            f"E91 lineage gap sample floor breached: {total} < {args.min_samples}",
            file=sys.stderr,
        )
        return 2

    bad_ids = { _pick(r, ("id", "lineage_id", "artifact_id", "name")) for r in rows if _is_gap(r) }
    bad_count = len(bad_ids)
    gap_rate = bad_count / total if total else 0.0

    if bad_count > args.max_gap_count or gap_rate > args.max_gap_rate:
        print(
            f"E91 lineage gap rate breach: count={bad_count} total={total} rate={gap_rate:.6f} "
            f"max_count={args.max_gap_count} max_rate={args.max_gap_rate}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

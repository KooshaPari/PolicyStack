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
        return [], f"E88 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("custody", "chains", "items", "records", "lineage"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E88 invalid input: expected list or dict with custody/chains/items/records/lineage"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _to_int(v: object) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _group_rows(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        group = _pick(
            row,
            (
                "lineage_id",
                "artifact_id",
                "custody_chain_id",
                "root_custody_id",
                "root_artifact_id",
            ),
        )
        if not group:
            group = _pick(row, ("chain_id", "id", "name"))
        if not group:
            group = "__orphan__"
        grouped.setdefault(group, []).append(row)
    return grouped


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--custody", required=True)
    p.add_argument("--max-continuity-breaks", type=int, default=0)
    args = p.parse_args()

    rows, err = _load_rows(pathlib.Path(args.custody))
    if err:
        print(err, file=sys.stderr)
        return 2

    known = {
        _pick(r, ("chain_id", "custody_chain_id", "id", "segment_id"))
        for r in rows
    }
    known.discard("")

    breaks = set()
    for r in rows:
        cid = _pick(r, ("chain_id", "custody_chain_id", "id", "segment_id"))
        parent = _pick(r, ("parent_chain_id", "previous_chain_id", "prev_chain_id"))
        if parent and parent not in known:
            if cid:
                breaks.add(cid)

        expected = _to_int(r.get("sequence") or r.get("step") or r.get("index") or r.get("seq"))
        if expected is None and (r.get("sequence") is not None or r.get("step") is not None or r.get("index") is not None or r.get("seq") is not None):
            if cid:
                breaks.add(cid)

    for _, records in _group_rows(rows).items():
        sequences: dict[int, list[str]] = {}
        for r in records:
            cid = _pick(r, ("chain_id", "custody_chain_id", "id", "segment_id"))
            seq = _to_int(r.get("sequence") or r.get("step") or r.get("index") or r.get("seq"))
            if seq is not None:
                sequences.setdefault(seq, []).append(cid)
        if not sequences:
            continue
        values = sorted(sequences.items())
        # Require contiguous sequence progression when sequence is provided.
        for index, (seq, ids) in enumerate(values, start=0):
            if index > 0 and seq != values[index - 1][0] + 1:
                breaks.update(ids)
        # Duplicate sequence numbers indicate chain continuity loss.
        for ids in sequences.values():
            if len(ids) > 1:
                breaks.update(ids)

    if len(breaks) > args.max_continuity_breaks:
        print(f"E88 custody chain continuity breach: {len(breaks)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

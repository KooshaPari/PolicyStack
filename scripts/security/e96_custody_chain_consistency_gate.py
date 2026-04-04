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
        return [], f"E96 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("custody", "chains", "items", "records", "entries", "lineage"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E96 invalid input: expected list or dict with "
        "custody/chains/items/records/entries/lineage",
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


def _to_int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        key = _pick(
            row,
            (
                "custody_chain_id",
                "lineage_id",
                "chain_root",
                "artifact_id",
                "root_artifact_id",
            ),
        )
        if not key:
            key = _pick(row, ("chain_id", "id", "name"))
        if not key:
            key = "__orphan__"
        grouped.setdefault(key, []).append(row)
    return grouped


def _build_digest_map(rows: list[dict]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for row in rows:
        rid = _pick(row, ("chain_id", "custody_chain_id", "segment_id", "id"))
        digest = _pick(row, ("segment_digest", "chain_digest", "hash", "checksum"))
        if rid and digest:
            digests[rid] = digest
    return digests


def _is_consistent(
    row: dict, known_ids: set[str], id_to_digest: dict[str, str]
) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"broken", "invalid", "missing", "inconsistent", "failed"}:
        return True
    if bool(row.get("inconsistent") or row.get("consistency_breach")):
        return True

    parent_id = _pick(row, ("parent_chain_id", "previous_chain_id", "prev_chain_id"))
    if parent_id and parent_id not in known_ids:
        return True

    parent_digest = _pick(row, ("parent_digest", "previous_hash", "prev_digest"))
    if parent_id and parent_digest:
        if parent_id not in id_to_digest:
            return True
        if parent_digest != id_to_digest[parent_id]:
            return True

    expected_seq = _to_int(row.get("sequence") or row.get("step") or row.get("index"))
    if expected_seq is None and any(
        row.get(key) is not None for key in ("sequence", "step", "index")
    ):
        return True

    return False


def _sequence_breaches(rows: list[dict]) -> set[str]:
    breaks: set[str] = set()
    for _, group in _group(rows).items():
        seq_map: dict[int, str] = {}
        ordered = sorted(
            group,
            key=lambda r: _to_int(
                r.get("sequence") or r.get("step") or r.get("index")
            )
            or 0,
        )
        for index, row in enumerate(ordered):
            cid = _pick(row, ("chain_id", "custody_chain_id", "segment_id", "id"))
            if not cid:
                continue
            seq = _to_int(row.get("sequence") or row.get("step") or row.get("index"))
            if seq is None:
                continue

            if seq in seq_map:
                breaks.add(cid)
                breaks.add(seq_map[seq])

            if index > 0:
                prev_seq = _to_int(
                    ordered[index - 1].get("sequence")
                    or ordered[index - 1].get("step")
                    or ordered[index - 1].get("index")
                )
                if prev_seq is not None and seq > prev_seq + 1:
                    breaks.add(cid)

            seq_map[seq] = cid
    return breaks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custody", required=True)
    parser.add_argument("--max-inconsistent-chains", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.custody))
    if err:
        print(err, file=sys.stderr)
        return 2

    known = {
        _pick(r, ("chain_id", "custody_chain_id", "segment_id", "id")) for r in rows
    }
    known.discard("")
    id_to_digest = _build_digest_map(rows)

    breaches = {
        _pick(r, ("chain_id", "custody_chain_id", "segment_id", "id"))
        for r in rows
        if _is_consistent(r, known, id_to_digest)
        and _pick(r, ("chain_id", "custody_chain_id", "segment_id", "id"))
    }
    breaches |= _sequence_breaches(rows)

    if len(breaches) > args.max_inconsistent_chains:
        print(
            f"E96 custody chain consistency breach: {len(breaches)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

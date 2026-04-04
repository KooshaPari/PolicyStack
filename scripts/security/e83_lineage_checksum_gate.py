#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import pathlib
import sys


def _load_rows(path: pathlib.Path) -> tuple[list[dict], str | None]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.open())), None
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"E83 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("lineage", "items", "records", "entries", "chains"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E83 invalid input: expected list or dict with lineage/items/records/entries/chains"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalized_payload(row: dict) -> str:
    payload = row.get("payload") or row.get("content") or row.get("data") or row.get("evidence") or {}
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return str(payload)


def _checksum_matches(row: dict) -> bool:
    checksum = _pick(row, ("checksum", "lineage_checksum", "sha256", "hash"))
    if not checksum:
        return False
    if len(checksum) < 16:
        return False
    expected_checksum = _pick(row, ("calculated_checksum", "expected_checksum"))
    if expected_checksum:
        return checksum.lower() == expected_checksum.lower()
    payload = row.get("payload") or row.get("content") or row.get("data") or row.get("evidence")
    if payload is None:
        return False
    expected = hashlib.sha256(_normalized_payload(row).encode("utf-8")).hexdigest()
    return checksum.lower() == expected


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lineage", required=True)
    p.add_argument("--max-bad-checksums", type=int, default=0)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.lineage))
    if err:
        print(err, file=sys.stderr)
        return 2
    bad = sorted(
        {
            _pick(r, ("id", "lineage_id", "artifact_id", "name"))
            for r in rows
            if not _checksum_matches(r)
        }
    )
    if len(bad) > args.max_bad_checksums:
        print(f"E83 lineage checksum gate breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

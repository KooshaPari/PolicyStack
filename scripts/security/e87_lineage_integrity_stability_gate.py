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
        return [], f"E87 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("lineage", "records", "items", "entries", "events"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E87 invalid input: expected list or dict with lineage/records/items/entries/events"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_float(v: object) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_unstable(row: dict, min_stability: float) -> bool:
    if str(row.get("integrity_status", "")).strip().lower() in {"broken", "mismatch", "tampered", "invalid", "unstable"}:
        return True
    if str(row.get("stability", "")).strip().lower() in {"false", "broken", "degraded"}:
        return True
    stability = _parse_float(row.get("stability_score") or row.get("integrity_score") or row.get("stability"))
    if stability is None:
        return True
    return stability < min_stability


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lineage", required=True)
    p.add_argument("--max-unstable", type=int, default=0)
    p.add_argument("--min-stability", type=float, default=0.95)
    args = p.parse_args()

    rows, err = _load_rows(pathlib.Path(args.lineage))
    if err:
        print(err, file=sys.stderr)
        return 2

    unstable = sorted(
        {
            _pick(r, ("lineage_id", "artifact_id", "record_id", "id", "name"))
            for r in rows
            if _is_unstable(r, args.min_stability)
        }
    )
    if len(unstable) > args.max_unstable:
        print(f"E87 lineage integrity stability breach: {len(unstable)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        return [], f"E86 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("failovers", "trust_failovers", "items", "events", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E86 invalid input: expected list or dict with failovers/trust_failovers/items/events/records"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_entropy(row: dict) -> float | None:
    for key in ("entropy", "entropy_score", "failover_entropy", "trust_entropy", "entropy_index"):
        value = row.get(key)
        if value is None or str(value).strip() == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _is_entropy_breach(row: dict, min_entropy: float) -> bool:
    if str(row.get("status", "")).strip().lower() in {"failed", "degraded", "breached", "insufficient"}:
        return True
    if str(row.get("entropy_state", "")).strip().lower() in {"low", "degraded", "insufficient"}:
        return True
    if bool(row.get("entropy_breach") or row.get("entropy_alert") or row.get("drift")):
        return True

    value = _parse_entropy(row)
    if value is None:
        return True
    return value < min_entropy


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--failovers", required=True)
    p.add_argument("--max-low-entropy", type=int, default=0)
    p.add_argument("--min-entropy", type=float, default=0.60)
    args = p.parse_args()

    rows, err = _load_rows(pathlib.Path(args.failovers))
    if err:
        print(err, file=sys.stderr)
        return 2

    bad = sorted(
        {
            _pick(r, ("failover_id", "id", "event_id", "name"))
            for r in rows
            if _is_entropy_breach(r, args.min_entropy)
        }
    )
    if len(bad) > args.max_low_entropy:
        print(f"E86 trust failover entropy breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

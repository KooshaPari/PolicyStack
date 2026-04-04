#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> "None":
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D69 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D69 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D69 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D69 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D69 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--inventory-csv", required=True)
    parser.add_argument("--max-stale", type=int, default=0)
    parser.add_argument("--max-missing-owner", type=int, default=0)
    parser.add_argument("--max-missing-ticket", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.inventory_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "inventory")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"override_id", "owner", "ticket", "status"},
    )

    stale = 0
    missing_owner = 0
    missing_ticket = 0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status in {"stale", "expired"}:
            stale += 1
        if not (row.get("owner") or "").strip():
            missing_owner += 1
        if not (row.get("ticket") or "").strip():
            missing_ticket += 1

    stale = max(stale, int(report.get("stale_overrides", 0)))
    missing_owner = max(missing_owner, int(report.get("missing_override_owner", 0)))
    missing_ticket = max(missing_ticket, int(report.get("missing_override_ticket", 0)))

    if stale > args.max_stale:
        _fail(f"D69 override inventory hygiene gate failed: stale={stale}")
    if missing_owner > args.max_missing_owner:
        _fail(
            f"D69 override inventory hygiene gate failed: "
            f"missing_owner={missing_owner}"
        )
    if missing_ticket > args.max_missing_ticket:
        _fail(
            f"D69 override inventory hygiene gate failed: "
            f"missing_ticket={missing_ticket}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

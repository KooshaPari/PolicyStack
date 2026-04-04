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
        _fail(f"D70 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D70 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D70 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required_headers - headers)
            if missing:
                _fail(f"D70 CSV missing headers {missing}: {path}")
            rows = list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D70 invalid CSV {path}: {exc}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--suppressions-csv", required=True)
    parser.add_argument("--max-expired", type=int, default=0)
    parser.add_argument("--max-missing-owner", type=int, default=0)
    parser.add_argument("--max-missing-rationale", type=int, default=0)
    parser.add_argument("--min-quality-score", type=float, default=1.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.suppressions_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "suppressions")

    report = _load_json(report_path)
    rows = _load_csv(
        csv_path,
        {"suppression_id", "owner", "rationale", "status"},
    )

    expired = 0
    missing_owner = 0
    missing_rationale = 0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status == "expired":
            expired += 1
        if not (row.get("owner") or "").strip():
            missing_owner += 1
        if not (row.get("rationale") or "").strip():
            missing_rationale += 1

    expired = max(expired, int(report.get("expired_suppressions", 0)))
    missing_owner = max(missing_owner, int(report.get("suppression_missing_owner", 0)))
    missing_rationale = max(
        missing_rationale,
        int(report.get("suppression_missing_rationale", 0)),
    )
    quality_score = float(report.get("suppression_expiry_quality_score", 1.0))

    if expired > args.max_expired:
        _fail(f"D70 suppression expiry quality gate failed: expired={expired}")
    if missing_owner > args.max_missing_owner:
        _fail(
            f"D70 suppression expiry quality gate failed: "
            f"missing_owner={missing_owner}"
        )
    if missing_rationale > args.max_missing_rationale:
        _fail(
            f"D70 suppression expiry quality gate failed: "
            f"missing_rationale={missing_rationale}"
        )
    if quality_score < args.min_quality_score:
        _fail(
            f"D70 suppression expiry quality gate failed: "
            f"quality_score={quality_score}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

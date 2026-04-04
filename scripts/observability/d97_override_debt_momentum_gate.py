#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"D97 override debt momentum gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D97 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D97 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        _fail(f"D97 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                _fail(f"D97 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D97 invalid override CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D97 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        _fail(f"D97 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--overrides-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--value-field", default="debt_score")
    parser.add_argument("--status-field", default="status")
    parser.add_argument("--max-max-momentum", type=float, default=0.0)
    parser.add_argument("--max-positive-momentum-steps", type=int, default=0)
    parser.add_argument("--max-momentum-breaches", type=int, default=0)
    parser.add_argument("--momentum-field", default="momentum")
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.overrides_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "overrides")

    report = _load_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field, args.status_field})
    if not rows:
        _fail("D97 override debt momentum gate failed: empty override csv")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or "").strip())
    values = [_to_float(row.get(args.value_field, ""), csv_path, args.value_field) for row in ordered]
    if len(values) < 2:
        _fail("D97 override debt momentum gate failed: insufficient override debt points")

    reported_momentum = float(report.get("override_debt_momentum", 0.0))
    breaches = _to_int(str(report.get("override_debt_momentum_breaches", 0)), csv_path, "override_debt_momentum_breaches")

    max_momentum = 0.0
    positive_steps = 0
    for current, following in zip(values, values[1:]):
        raw_delta = following - current
        momentum = abs(raw_delta)
        if args.momentum_field and args.momentum_field in rows[0]:
            pass
        max_momentum = max(max_momentum, momentum)
        if raw_delta > 0:
            positive_steps += 1

    if max_momentum > reported_momentum:
        reported_momentum = max_momentum
    if args.momentum_field and any(
        row.get(args.momentum_field, "").strip() for row in ordered
    ):
        for row in ordered:
            explicit = _to_float(row.get(args.momentum_field, ""), csv_path, args.momentum_field)
            if explicit > args.max_max_momentum:
                breaches += 1
            max_momentum = max(max_momentum, explicit)

    if max_momentum > args.max_max_momentum:
        _fail(f"D97 override debt momentum gate failed: max_momentum={max_momentum}")
    if positive_steps > args.max_positive_momentum_steps:
        _fail(f"D97 override debt momentum gate failed: positive_momentum_steps={positive_steps}")
    if breaches > args.max_momentum_breaches:
        _fail(f"D97 override debt momentum gate failed: momentum_breaches={breaches}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

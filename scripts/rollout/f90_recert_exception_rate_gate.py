#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def fail(msg: str) -> None:
    print(f'F90 recert exception rate gate failed: {msg}', file=sys.stderr)
    raise SystemExit(2)

def to_int(value: str, field: str) -> int:
    try:
        return int((value or '').strip())
    except ValueError:
        fail(f'invalid integer in {field}: {value!r}')

def normalized_csv_rows(path: pathlib.Path, expected: list[str]) -> list[dict]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    if not rows:
        return []
    if list(rows[0].keys()) != expected:
        fail(f'invalid exceptions csv header: {list(rows[0].keys())}')
    for row in rows:
        row['days_open'] = to_int(row.get('days_open'), 'days_open')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--recert', required=True)
    parser.add_argument('--exceptions-csv', required=True)
    parser.add_argument('--max-exception-rate', type=float, default=0.0)
    parser.add_argument('--max-overdue-open-days', type=int, default=14)
    args = parser.parse_args()

    try:
        config = json.loads(pathlib.Path(args.recert).read_text())
    except Exception:
        fail('invalid recert json')
    if not isinstance(config, dict) or bool(config.get('exception_rate_tracking_enabled', True)) is not True:
        fail('exception_rate_tracking_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.exceptions_csv),
        ['exception_id', 'status', 'is_mitigated', 'days_open', 'owner'],
    )
    open_exceptions = [r for r in rows if (r.get('status') or '').strip().lower() != 'resolved']
    unmitigated = [r for r in open_exceptions if (r.get('is_mitigated') or '').strip().lower() not in {'true', 'yes', '1'}]
    stale = [r for r in open_exceptions if r['days_open'] > args.max_overdue_open_days]
    open_count = len(open_exceptions)
    rate = (len(unmitigated) / open_count) if open_count else 0.0
    if rate > args.max_exception_rate or stale:
        fail(f'open_exceptions={open_count} unmitigated_exceptions={len(unmitigated)} '
             f'exception_rate={rate:.6f} max_exception_rate={args.max_exception_rate} '
             f'overdue_open_exceptions={len(stale)} max_overdue_open_days={args.max_overdue_open_days}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

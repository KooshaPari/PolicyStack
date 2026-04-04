#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(msg: str) -> None:
    print(f'F98 recert exception staleness gate failed: {msg}', file=sys.stderr)
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
    parser.add_argument('--max-stale-exceptions', type=int, default=0)
    parser.add_argument('--max-stale-days', type=int, default=30)
    parser.add_argument('--max-unresolved-exceptions', type=int, default=0)
    args = parser.parse_args()

    try:
        config = json.loads(pathlib.Path(args.recert).read_text())
    except Exception:
        fail('invalid recert json')
    if not isinstance(config, dict) or bool(config.get('exception_staleness_tracking_enabled', True)) is not True:
        fail('exception_staleness_tracking_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.exceptions_csv),
        ['exception_id', 'status', 'is_mitigated', 'days_open', 'owner'],
    )
    unresolved = [row for row in rows if (row.get('status') or '').strip().lower() != 'resolved']
    stale = [row for row in unresolved if row['days_open'] > args.max_stale_days]
    if (
        len(stale) > args.max_stale_exceptions
        or len(unresolved) > args.max_unresolved_exceptions
    ):
        fail(
            f'unresolved_exceptions={len(unresolved)} stale_exceptions={len(stale)} '
            f'max_stale_exceptions={args.max_stale_exceptions} '
            f'max_stale_days={args.max_stale_days} '
            f'max_unresolved_exceptions={args.max_unresolved_exceptions}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

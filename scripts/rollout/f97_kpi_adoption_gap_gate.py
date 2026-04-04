#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(msg: str) -> None:
    print(f'F97 KPI adoption gap gate failed: {msg}', file=sys.stderr)
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
        fail(f'invalid adoption gaps csv header: {list(rows[0].keys())}')
    for row in rows:
        row['days_open'] = to_int(row.get('days_open'), 'days_open')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--kpi', required=True)
    parser.add_argument('--adoptions-csv', required=True)
    parser.add_argument('--max-open-gaps', type=int, default=0)
    parser.add_argument('--max-critical-gap-ratio', type=float, default=0.0)
    parser.add_argument('--max-open-days', type=int, default=21)
    args = parser.parse_args()

    try:
        config = json.loads(pathlib.Path(args.kpi).read_text())
    except Exception:
        fail('invalid kpi json')
    if not isinstance(config, dict) or bool(config.get('kpi_adoption_tracking_enabled', True)) is not True:
        fail('kpi_adoption_tracking_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.adoptions_csv),
        ['kpi_id', 'gap_status', 'criticality', 'owner', 'days_open'],
    )
    open_gaps = [row for row in rows if (row.get('gap_status') or '').strip().lower() != 'filled']
    critical_gaps = [row for row in rows if (row.get('criticality') or '').strip().lower() == 'critical']
    critical_open = [
        row for row in critical_gaps
        if (row.get('gap_status') or '').strip().lower() != 'filled'
    ]
    stale_open = [row for row in open_gaps if row['days_open'] > args.max_open_days]
    critical_ratio = (len(critical_open) / len(critical_gaps)) if critical_gaps else 0.0

    if (
        len(open_gaps) > args.max_open_gaps
        or critical_ratio > args.max_critical_gap_ratio
        or stale_open
    ):
        fail(
            f'open_gaps={len(open_gaps)} critical_gaps={len(critical_gaps)} '
            f'critical_gap_ratio={critical_ratio:.6f} max_open_gaps={args.max_open_gaps} '
            f'max_critical_gap_ratio={args.max_critical_gap_ratio} '
            f'stale_open_gaps={len(stale_open)} max_open_days={args.max_open_days}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

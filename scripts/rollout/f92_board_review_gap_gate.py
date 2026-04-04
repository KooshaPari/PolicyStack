#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def fail(msg: str) -> None:
    print(f'F92 board review gap gate failed: {msg}', file=sys.stderr)
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
        fail(f'invalid reviews csv header: {list(rows[0].keys())}')
    for row in rows:
        row['days_since_last_review'] = to_int(row.get('days_since_last_review'), 'days_since_last_review')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--board', required=True)
    parser.add_argument('--reviews-csv', required=True)
    parser.add_argument('--max-open-gaps', type=int, default=0)
    parser.add_argument('--max-gap-days', type=int, default=21)
    args = parser.parse_args()
    try:
        config = json.loads(pathlib.Path(args.board).read_text())
    except Exception:
        fail('invalid board json')
    if not isinstance(config, dict) or bool(config.get('board_review_gap_tracking_enabled', True)) is not True:
        fail('board_review_gap_tracking_enabled != true')
    rows = normalized_csv_rows(
        pathlib.Path(args.reviews_csv),
        ['review_id', 'status', 'days_since_last_review', 'reviewer'],
    )
    open_reviews = [r for r in rows if (r.get('status') or '').strip().lower() not in {'complete', 'completed'}]
    overdue = [r for r in open_reviews if r['days_since_last_review'] > args.max_gap_days]
    if len(open_reviews) > args.max_open_gaps or overdue:
        fail(f'open_gaps={len(open_reviews)} overdue_gaps={len(overdue)} '
             f'max_open_gaps={args.max_open_gaps} max_gap_days={args.max_gap_days}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

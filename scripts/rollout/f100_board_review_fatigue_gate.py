#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(msg: str) -> None:
    print(f'F100 board review fatigue gate failed: {msg}', file=sys.stderr)
    raise SystemExit(2)


def to_float(value: str, field: str) -> float:
    try:
        return float((value or '').strip())
    except ValueError:
        fail(f'invalid float in {field}: {value!r}')


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
        row['fatigue_score'] = to_float(row.get('fatigue_score'), 'fatigue_score')
        row['days_since_review'] = to_int(row.get('days_since_review'), 'days_since_review')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--board', required=True)
    parser.add_argument('--reviews-csv', required=True)
    parser.add_argument('--max-fatigued-reviews', type=int, default=0)
    parser.add_argument('--max-fatigue-score', type=float, default=1.0)
    parser.add_argument('--max-review-age-days', type=int, default=60)
    args = parser.parse_args()

    try:
        board = json.loads(pathlib.Path(args.board).read_text())
    except Exception:
        fail('invalid board json')
    if not isinstance(board, dict) or bool(board.get('board_review_fatigue_monitoring_enabled', True)) is not True:
        fail('board_review_fatigue_monitoring_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.reviews_csv),
        ['review_id', 'status', 'days_since_review', 'fatigue_score', 'reviewer'],
    )
    active = [
        row for row in rows
        if (row.get('status') or '').strip().lower() not in {'complete', 'closed'}
    ]
    fatigued = [row for row in active if row['fatigue_score'] > args.max_fatigue_score]
    stale = [row for row in active if row['days_since_review'] > args.max_review_age_days]
    if stale or len(fatigued) > args.max_fatigued_reviews:
        fail(
            f'active_reviews={len(active)} fatigued_reviews={len(fatigued)} '
            f'fatigue_score_limit={args.max_fatigue_score} '
            f'stale_reviews={len(stale)} max_review_age_days={args.max_review_age_days} '
            f'max_fatigued_reviews={args.max_fatigued_reviews}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

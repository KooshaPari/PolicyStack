#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--board', required=True); p.add_argument('--reviews-csv', required=True); p.add_argument('--max-review-overdue-days', type=int, default=30); p.add_argument('--max-overdue-reviews', type=int, default=0); a=p.parse_args()
try:
    b=json.loads(pathlib.Path(a.board).read_text())
except Exception:
    print('F88 board review overdue gate failed: invalid board json', file=sys.stderr); raise SystemExit(2)
if not isinstance(b, dict) or bool(b.get('review_overdue_monitoring_enabled', True)) is not True:
    print('F88 board review overdue gate failed: review_overdue_monitoring_enabled != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.reviews_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['review_id','status','days_overdue','reviewer']:
    print('F88 board review overdue gate failed: invalid reviews csv header', file=sys.stderr); raise SystemExit(2)
overdue=[x for x in r if (x.get('status') or '').strip().lower() not in {'complete','completed'} or int((x.get('days_overdue') or '9999').strip())>a.max_review_overdue_days]
if len(overdue)>a.max_overdue_reviews:
    print(f'F88 board review overdue gate failed: overdue_reviews={len(overdue)} > {a.max_overdue_reviews}', file=sys.stderr); raise SystemExit(2)

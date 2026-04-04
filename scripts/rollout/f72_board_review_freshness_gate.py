#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--board', required=True); p.add_argument('--reviews-csv', required=True); p.add_argument('--max-days-since-review', type=int, default=30); a=p.parse_args()
b=json.loads(pathlib.Path(a.board).read_text())
if not isinstance(b, dict):
    print('F72 board review freshness gate failed: invalid board json', file=sys.stderr); raise SystemExit(2)
if int(b.get('days_since_last_review', 9999))>a.max_days_since_review:
    print('F72 board review freshness gate failed: board days_since_last_review exceeded', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.reviews_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['review_id','status','days_since_review']:
    print('F72 board review freshness gate failed: invalid reviews csv header', file=sys.stderr); raise SystemExit(2)
s=sum(1 for x in r if (x.get('status') or '').strip().lower()!='complete' or int((x.get('days_since_review') or '9999').strip())>a.max_days_since_review)
if s>0:
    print(f'F72 board review freshness gate failed: stale_or_incomplete_reviews={s}', file=sys.stderr); raise SystemExit(2)

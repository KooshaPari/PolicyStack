#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--board', required=True); p.add_argument('--reviews-csv', required=True); p.add_argument('--max-review-latency-days', type=int, default=14); a=p.parse_args()
try:
    b=json.loads(pathlib.Path(a.board).read_text())
except Exception:
    print('F80 board review latency gate failed: invalid board json', file=sys.stderr); raise SystemExit(2)
if not isinstance(b, dict) or bool(b.get('review_latency_monitoring_enabled', True)) is not True:
    print('F80 board review latency gate failed: review_latency_monitoring_enabled != true', file=sys.stderr); raise SystemExit(2)
r=list(csv.DictReader(pathlib.Path(a.reviews_csv).read_text().splitlines()))
if not r or list(r[0].keys())!=['review_id','status','latency_days']:
    print('F80 board review latency gate failed: invalid reviews csv header', file=sys.stderr); raise SystemExit(2)
late=sum(1 for x in r if (x.get('status') or '').strip().lower() not in {'complete','completed'} or int((x.get('latency_days') or '9999').strip())>a.max_review_latency_days)
if late>0:
    print(f'F80 board review latency gate failed: late_or_incomplete_reviews={late}', file=sys.stderr); raise SystemExit(2)

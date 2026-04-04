#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--board', required=True); p.add_argument('--max-days-since', type=int, default=30); a=p.parse_args()
b=json.loads(pathlib.Path(a.board).read_text())
if int(b.get('days_since_last_review',9999))>a.max_days_since:
    print('F64 board cadence gate failed', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--attestations', required=True); p.add_argument('--lead-key', default='lead_time_hours'); p.add_argument('--min-lead-hours', type=float, default=0.0); p.add_argument('--max-breaches', type=int, default=0); a=p.parse_args()
items=json.loads(pathlib.Path(a.attestations).read_text()) 
if isinstance(items,dict): items=[items]
breaches=sum(1 for i in items if float(i.get(a.lead_key,0) or 0)<a.min_lead_hours)
if breaches>a.max_breaches:
    print('B75 attestation lead time gate failed', file=sys.stderr); raise SystemExit(2)

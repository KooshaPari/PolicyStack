#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--report', required=True); p.add_argument('--max-regressions', type=int, default=0); a=p.parse_args()
r=json.loads(pathlib.Path(a.report).read_text())
regressions=int(float(r.get('compatibility_regressions', r.get('schema_regressions', 0))))
if regressions>a.max_regressions:
    print('A74 schema compatibility regression gate failed', file=sys.stderr); raise SystemExit(2)

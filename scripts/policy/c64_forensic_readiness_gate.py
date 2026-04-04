#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--status', required=True); a=p.parse_args()
s=json.loads(pathlib.Path(a.status).read_text())
if not bool(s.get('forensic_pack_ready',False)):
    print('C64 forensic readiness failed', file=sys.stderr); raise SystemExit(2)

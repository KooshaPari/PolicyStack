#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--overrides', required=True); a=p.parse_args()
ov=json.loads(pathlib.Path(a.overrides).read_text())
if any(o.get('expires_at') in (None,'') for o in ov):
    print('D57 override hardstop failed', file=sys.stderr); raise SystemExit(2)

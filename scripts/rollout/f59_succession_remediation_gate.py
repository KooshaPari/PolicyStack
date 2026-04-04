#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--records', required=True); a=p.parse_args()
r=json.loads(pathlib.Path(a.records).read_text())
if any(not x.get('remediation_closed') for x in r):
    print('F59 open succession remediation items', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
p=argparse.ArgumentParser(); p.add_argument('--schema', required=True); a=p.parse_args()
s=json.loads(pathlib.Path(a.schema).read_text())
expired=[f for f in s.get('deprecated',[]) if f.get('grace_expired')]
if expired:
    print(f'A58 deprecated fields expired: {len(expired)}', file=sys.stderr); raise SystemExit(2)

#!/usr/bin/env python3
import argparse
import json
import pathlib
p=argparse.ArgumentParser(); p.add_argument('--events', required=True); p.add_argument('--out', default='artifacts/c/c60-pack.jsonl'); a=p.parse_args()
events=json.loads(pathlib.Path(a.events).read_text())
o=pathlib.Path(a.out); o.parent.mkdir(parents=True, exist_ok=True)
with o.open('w') as f:
    for e in events: f.write(json.dumps(e)+'\n')

#!/usr/bin/env python3
import argparse
import json
import pathlib

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--exceptions', required=True); p.add_argument('--out', default='artifacts/f/f54-retirement.json'); args=p.parse_args()
    exc=json.loads(pathlib.Path(args.exceptions).read_text())
    retire=[e for e in exc if e.get('age_days',0)>90 and not e.get('justified')]
    o=pathlib.Path(args.out); o.parent.mkdir(parents=True, exist_ok=True); o.write_text(json.dumps({'task':'F54','retire':retire}, indent=2)+'\n')
    return 0
if __name__=='__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
import pathlib

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--actions', required=True)
    p.add_argument('--out', default='artifacts/d/d56-recertify.json')
    args=p.parse_args()
    actions=json.loads(pathlib.Path(args.actions).read_text())
    passed=[a for a in actions if a.get('verified')]
    o=pathlib.Path(args.out); o.parent.mkdir(parents=True, exist_ok=True)
    o.write_text(json.dumps({'task':'D56','verified_count':len(passed),'total':len(actions)}, indent=2)+'\n')
    return 0
if __name__=='__main__':
    raise SystemExit(main())

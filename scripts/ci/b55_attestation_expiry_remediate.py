#!/usr/bin/env python3
import argparse
import json
import pathlib
import datetime

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--in', dest='inp', required=True)
    p.add_argument('--out', default='artifacts/b/b55-remediation-plan.json')
    p.add_argument('--warn-days', type=int, default=7)
    args=p.parse_args()
    data=json.loads(pathlib.Path(args.inp).read_text())
    now=datetime.datetime.utcnow().date()
    plan=[]
    for x in data:
        exp=datetime.date.fromisoformat(x['expires_on'])
        days=(exp-now).days
        if days <= args.warn_days:
            plan.append({'id':x['id'],'action':'reissue','days_left':days})
    out=pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'task':'B55','plan':plan}, indent=2)+'\n')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

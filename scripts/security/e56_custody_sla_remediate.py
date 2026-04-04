#!/usr/bin/env python3
import argparse
import json
import pathlib

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--breaches', required=True); p.add_argument('--out', default='artifacts/e/e56-remediation.json'); args=p.parse_args()
    b=json.loads(pathlib.Path(args.breaches).read_text())
    plan=[{'id':x['id'],'action':'contain+notify'} for x in b if x.get('sla_breached')]
    o=pathlib.Path(args.out); o.parent.mkdir(parents=True, exist_ok=True); o.write_text(json.dumps({'task':'E56','plan':plan}, indent=2)+'\n')
    return 0
if __name__=='__main__':
    raise SystemExit(main())

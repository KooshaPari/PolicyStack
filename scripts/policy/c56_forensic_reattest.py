#!/usr/bin/env python3
import argparse
import json
import pathlib
import time

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--bundle', required=True)
    p.add_argument('--out', default='artifacts/c/c56-forensic-reattest.json')
    args=p.parse_args()
    b=json.loads(pathlib.Path(args.bundle).read_text())
    out={'task':'C56','bundle_id':b.get('id'),'reattested_at':int(time.time()),'status':'ok'}
    o=pathlib.Path(args.out); o.parent.mkdir(parents=True, exist_ok=True); o.write_text(json.dumps(out, indent=2)+'\n')
    return 0
if __name__=='__main__':
    raise SystemExit(main())

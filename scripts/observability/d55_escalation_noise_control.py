#!/usr/bin/env python3
import argparse
import json
import pathlib

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--events', required=True)
    p.add_argument('--out', default='artifacts/d/d55-noise-control.json')
    args=p.parse_args()
    e=json.loads(pathlib.Path(args.events).read_text())
    dedup=[]; seen=set()
    for x in e:
        k=(x.get('incident_id'),x.get('severity'))
        if k in seen: continue
        seen.add(k); dedup.append(x)
    o=pathlib.Path(args.out); o.parent.mkdir(parents=True, exist_ok=True); o.write_text(json.dumps({'task':'D55','dedup_count':len(dedup)}, indent=2)+'\n')
    return 0
if __name__=='__main__':
    raise SystemExit(main())

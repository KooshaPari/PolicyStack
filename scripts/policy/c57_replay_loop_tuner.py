#!/usr/bin/env python3
import argparse
import json
import pathlib
p=argparse.ArgumentParser(); p.add_argument('--input', required=True); p.add_argument('--out', default='artifacts/c/c57-tuning.json'); a=p.parse_args()
d=json.loads(pathlib.Path(a.input).read_text())
res={'task':'C57','new_backoff':max(1,int(d.get('error_rate',1)*10))}
o=pathlib.Path(a.out); o.parent.mkdir(parents=True, exist_ok=True); o.write_text(json.dumps(res,indent=2)+'\n')

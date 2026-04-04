#!/usr/bin/env python3
import argparse
import json
import pathlib
p=argparse.ArgumentParser(); p.add_argument('--incidents', required=True); p.add_argument('--out', default='artifacts/b/b59-drill.json'); a=p.parse_args()
inc=json.loads(pathlib.Path(a.incidents).read_text())
out={'task':'B59','handled':len([i for i in inc if i.get('expired')])}
op=pathlib.Path(a.out); op.parent.mkdir(parents=True, exist_ok=True); op.write_text(json.dumps(out,indent=2)+'\n')

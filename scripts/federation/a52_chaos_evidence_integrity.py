#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib

def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True)
    p.add_argument("--out", default="artifacts/a/a52-chaos-integrity.json")
    args = p.parse_args()
    d = pathlib.Path(args.dir)
    files = [f for f in d.rglob("*") if f.is_file()]
    report = {"task":"A52", "count": len(files), "files": [{"path":str(f), "sha256":sha256(f)} for f in files]}
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=2)+"\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

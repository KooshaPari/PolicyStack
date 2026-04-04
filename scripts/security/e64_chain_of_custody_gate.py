#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

p = argparse.ArgumentParser()
p.add_argument("--custody", required=True)
a = p.parse_args()
c = json.loads(pathlib.Path(a.custody).read_text())
if not bool(c.get("all_signed", False)):
    print("E64 chain of custody incomplete", file=sys.stderr)
    raise SystemExit(2)

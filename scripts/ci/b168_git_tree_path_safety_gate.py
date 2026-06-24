#!/usr/bin/env python3
"""Regression guard: block CRLF / wildcard contamination in git tree paths.

Tracks issue #52: a past bug embedded ``\\r`` (CR) and shell-glob characters
(``*``, ``?``, ``[``) into git tree-entry paths, breaking Windows checkouts
and ``git subtree add``. This guard inspects every blob path in the current
``HEAD`` tree and fails CI if any forbidden character appears.

Exit codes:
  0  tree is clean
  2  forbidden characters detected (printed on stderr)
  3  git invocation failed
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Iterable

FORBIDDEN_CHARS: tuple[str, ...] = ("\r", "\n", "\t")
FORBIDDEN_GLOBS: tuple[str, ...] = ("*", "?", "[", "]", "{", "}", "\\")


def iter_tree_paths(ref: str) -> Iterable[str]:
    """Yield every path recorded in the git tree at ``ref`` (recursive)."""
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", ref],
        check=True,
        capture_output=True,
        text=True,
    )
    for raw in proc.stdout.split("\x00"):
        if raw:
            yield raw


def scan(ref: str) -> list[tuple[str, str]]:
    """Return ``[(path, reason), ...]`` for every offending path."""
    bad: list[tuple[str, str]] = []
    for path in iter_tree_paths(ref):
        for ch in FORBIDDEN_CHARS:
            if ch in path:
                bad.append((path, f"contains control char {ch!r}"))
                break
        else:
            for ch in FORBIDDEN_GLOBS:
                if ch in path:
                    bad.append((path, f"contains shell-glob char {ch!r}"))
                    break
    return bad


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ref", default="HEAD", help="git ref to scan (default: HEAD)")
    args = p.parse_args()

    try:
        bad = scan(args.ref)
    except subprocess.CalledProcessError as exc:
        print(
            f"git ls-tree failed (rc={exc.returncode}): {exc.stderr}", file=sys.stderr
        )
        return 3

    if bad:
        print(
            f"CRLF/wildcard guard: {len(bad)} bad tree path(s) in {args.ref}:",
            file=sys.stderr,
        )
        for path, reason in bad:
            print(f"  - {path!r}: {reason}", file=sys.stderr)
        print(
            "Remediation: rewrite history with `git filter-repo` or "
            "`git fast-export | sed 's/\\r//' | git fast-import` "
            "and re-push.",
            file=sys.stderr,
        )
        return 2

    print(
        f"CRLF/wildcard guard: {args.ref} tree is clean ({sum(1 for _ in iter_tree_paths(args.ref))} paths scanned)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

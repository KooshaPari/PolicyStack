#!/usr/bin/env python3
"""Build a PR-ready patch package for this rollout."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts"
PATCH_FILE = OUT_DIR / "agent-devops-setups-pr-ready.patch"
MANIFEST_FILE = OUT_DIR / "agent-devops-setups-pr-package.json"


def git(cmd: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *cmd],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def run_diff(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result.stdout


def main() -> None:
    tracked_modified = git(["diff", "--name-only"])
    untracked = git(["ls-files", "-o", "--exclude-standard"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    patch_lines: list[str] = []
    manifest_entries = []

    for file_path in tracked_modified:
        diff = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--", file_path],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if diff:
            patch_lines.append(diff.rstrip())
            manifest_entries.append(
                {
                    "path": file_path,
                    "change_type": "modify",
                    "payload": "git diff",
                }
            )

    for file_path in untracked:
        if file_path.startswith("artifacts/"):
            continue
        diff = run_diff(
            [
                "git",
                "-C",
                str(ROOT),
                "diff",
                "--no-index",
                "--",
                "/dev/null",
                file_path,
            ]
        )
        if diff:
            patch_lines.append(diff.rstrip())
            manifest_entries.append(
                {
                    "path": file_path,
                    "change_type": "add",
                    "payload": "git diff --no-index",
                }
            )

    patch_text = "\n\n".join(patch_lines)
    PATCH_FILE.write_text(patch_text + "\n", encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "patch": str(PATCH_FILE.name),
        "root": str(ROOT),
        "entries": manifest_entries,
        "summary": {
            "tracked_modifications": len([e for e in manifest_entries if e["change_type"] == "modify"]),
            "new_files": len([e for e in manifest_entries if e["change_type"] == "add"]),
        },
    }

    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"generated patch: {PATCH_FILE}")
    print(f"generated manifest: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()

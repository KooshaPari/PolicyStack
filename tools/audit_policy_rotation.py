#!/usr/bin/env python3
"""Track effective policy digest drift across repos over time."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track and compare policy digest rotation per repository."
    )
    parser.add_argument(
        "--repo-list",
        required=True,
        help="Comma-separated repository ids",
    )
    parser.add_argument(
        "--repo-root",
        default="/Users/kooshapari/CodeProjects/Phenotype/repos",
        help="Workspace path containing repositories",
    )
    parser.add_argument(
        "--state",
        default="/tmp/policy-rotation-state.json",
        help="State file for previous digest snapshots",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional file to write rotation JSON report",
    )
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="Exit non-zero when any policy digest changed",
    )
    return parser.parse_args()


def read_digest(repo_root: Path) -> tuple[str | None, str | None]:
    payload_path = repo_root / "docs" / "agent-policy" / "effective-policy.json"
    if not payload_path.exists():
        return None, None
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    audit = payload.get("audit", {})
    return audit.get("policy_digest"), audit.get("generated_at")


def main() -> None:
    args = parse_args()
    repos = [r.strip() for r in args.repo_list.split(",") if r.strip()]
    base_dir = Path(args.repo_root)
    state_path = Path(args.state)
    previous: dict = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))

    generated_at = datetime.now(timezone.utc).isoformat()
    report: list[dict] = []
    changes = 0

    for repo in repos:
        repo_path = base_dir / repo
        digest, policy_time = read_digest(repo_path)
        prev_digest = previous.get(repo, {}).get("digest") if isinstance(previous, dict) else None
        changed = prev_digest is not None and digest is not None and prev_digest != digest
        created = prev_digest is None and digest is not None
        if changed or created:
            changes += 1

        report.append(
            {
                "repo": repo,
                "digest": digest,
                "policy_time": policy_time,
                "previous_digest": prev_digest,
                "changed": changed,
                "first_seen": created,
            }
        )

        previous[repo] = {
            "digest": digest,
            "last_seen": generated_at,
            "previous_snapshot_at": previous.get(repo, {}).get("last_seen")
            if isinstance(previous.get(repo), dict)
            else None,
            "policy_time": policy_time,
        }

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")

    payload = {"generated_at": generated_at, "changes": changes, "entries": report}
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))

    if changes and args.fail_on_change:
        print(f"policy rotation changes detected: {changes}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

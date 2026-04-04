#!/usr/bin/env python3
"""Run a compact end-to-end matrix across harness/runtime check surfaces."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    REPO_ROOT
    / "docs"
    / "sessions"
    / "20260306-authorization-vertical-slice"
    / "artifacts"
)
HARNESS_MATRIX = ["codex", "cursor-agent", "factory-droid", "claude-code"]
SCRIPT = [sys.executable, "-m", "policy_federation.cli"]


def _run_policy_cli(argv: list[str]) -> tuple[int, dict]:
    env = os.environ.copy()
    cli_src = str(REPO_ROOT / "cli" / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = cli_src if not existing else f"{cli_src}{os.pathsep}{existing}"
    result = subprocess.run(
        SCRIPT + argv,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    payload: dict = {}
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = {
                "parse_error": "stdout was not json",
                "stdout": result.stdout,
            }
    return result.returncode, payload


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base_case_kwargs = {
        "--domain": "devops",
        "--repo": "thegent",
    }
    cases = [
        {
            "name": "exec_allow_git_commit_in_worktree",
            "cmd": [
                "intercept",
                "--harness",
                "{harness}",
                "--action",
                "exec",
                "--command",
                "git commit -m e2e",
                "--cwd",
                "/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
                "--ask-mode",
                "fail",
            ],
            "expected": "allow",
        },
        {
            "name": "exec_deny_git_commit_outside_worktree",
            "cmd": [
                "intercept",
                "--harness",
                "{harness}",
                "--action",
                "exec",
                "--command",
                "git commit -m e2e",
                "--cwd",
                "/tmp",
                "--ask-mode",
                "fail",
            ],
            "expected": "deny",
        },
        {
            "name": "exec_ask_network_install",
            "cmd": [
                "intercept",
                "--harness",
                "{harness}",
                "--action",
                "exec",
                "--command",
                "uv pip install requests",
                "--cwd",
                "/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
                "--ask-mode",
                "allow",
            ],
            "expected": "allow",
        },
        {
            "name": "write_deny_outside_worktree",
            "cmd": [
                "write-check",
                "--harness",
                "{harness}",
                "--cwd",
                "/tmp",
                "--target-path",
                "/tmp/test.txt",
                "--ask-mode",
                "fail",
            ],
            "expected": "deny",
        },
        {
            "name": "network_check_ask_outside_allow_mode",
            "cmd": [
                "network-check",
                "--harness",
                "{harness}",
                "--command",
                "curl https://example.com",
                "--ask-mode",
                "fail",
                "--cwd",
                "/tmp",
            ],
            "expected": "ask",
        },
    ]

    matrix_rows = []
    failures = []

    for harness in HARNESS_MATRIX:
        for case in cases:
            base = []
            for key, value in base_case_kwargs.items():
                base.extend([key, value])
            cmd = [arg.format(harness=harness) for arg in case["cmd"]] + base
            return_code, payload = _run_policy_cli(cmd)
            final_decision = payload.get("final_decision", "error")
            policy_decision = payload.get("policy_decision", "error")
            row = {
                "harness": harness,
                "name": case["name"],
                "expected": case["expected"],
                "actual": final_decision,
                "policy_decision": policy_decision,
                "exit_code": return_code,
            }
            matrix_rows.append(row)
            if final_decision != case["expected"]:
                failures.append(row)

    result_payload = {
        "status": "fail" if failures else "pass",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": matrix_rows,
        "failures": failures,
    }

    json_path = ARTIFACT_DIR / "e2e_matrix.json"
    md_path = ARTIFACT_DIR / "e2e_matrix.md"
    json_path.write_text(json.dumps(result_payload, indent=2, sort_keys=True), encoding="utf-8")

    md_rows = []
    for row in matrix_rows:
        status = "PASS" if row["actual"] == row["expected"] else "FAIL"
        md_rows.append(
            f"| {row['harness']} | {row['name']} | {row['expected']} | "
            f"{row['actual']} | {row['exit_code']} | {status} |"
        )
    header = [
        "# e2e Policy Matrix",
        "",
        "| harness | case | expected | actual | exit_code | status |",
        "|---|---|---|---|---:|---|",
        *md_rows,
        "",
    ]
    md_path.write_text("\n".join(header), encoding="utf-8")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

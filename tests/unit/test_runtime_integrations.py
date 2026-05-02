from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from policy_federation.constants import DEFAULT_REVIEW_MODEL
from policy_federation.integrations import (
    install_runtime_integrations,
    uninstall_runtime_integrations,
)
from support import REPO_ROOT


class RuntimeIntegrationsTest(unittest.TestCase):
    def test_install_runtime_integrations_patches_home_configs(self) -> None:
        existing_pretool_command = '"$HOME/.claude/bin/hook-dispatcher" pretool'
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            (home / ".cursor").mkdir()
            (home / ".factory").mkdir()
            (home / ".codex").mkdir()
            (home / ".claude").mkdir()
            (home / ".local" / "bin").mkdir(parents=True)
            (home / ".local" / "share" / "uv" / "tools" / "thegent" / "bin").mkdir(
                parents=True,
            )
            (home / ".cursor" / "cli-config.json").write_text(
                json.dumps({"permissions": {"allow": [], "deny": []}, "version": 1}),
                encoding="utf-8",
            )
            (home / ".factory" / "settings.json").write_text(
                json.dumps({"commandAllowlist": [], "commandDenylist": []}),
                encoding="utf-8",
            )
            (home / ".codex" / "config.json").write_text(
                json.dumps({}), encoding="utf-8",
            )
            (home / ".codex" / "config.toml").write_text(
                f'model = "{DEFAULT_REVIEW_MODEL}"\n',
                encoding="utf-8",
            )
            (home / ".claude" / "settings.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": "Bash",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": existing_pretool_command,
                                        },
                                    ],
                                },
                            ],
                        },
                    },
                ),
                encoding="utf-8",
            )
            (home / ".local" / "bin" / "cursor").write_text(
                "#!/bin/sh\nexit 0\n",
                encoding="utf-8",
            )
            (home / ".local" / "bin" / "cursor").chmod(0o755)
            droid_binary = (
                home / ".local" / "share" / "uv" / "tools" / "thegent" / "bin" / "droid"
            )
            droid_binary.write_text(
                "#!/bin/sh\nexit 0\n",
                encoding="utf-8",
            )
            droid_binary.chmod(0o755)

            result = install_runtime_integrations(REPO_ROOT, home)

            cursor_payload = json.loads(
                (home / ".cursor" / "cli-config.json").read_text(encoding="utf-8"),
            )
            factory_payload = json.loads(
                (home / ".factory" / "settings.json").read_text(encoding="utf-8"),
            )
            codex_payload = json.loads(
                (home / ".codex" / "config.json").read_text(encoding="utf-8"),
            )
            codex_toml = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8"),
            )

            assert result["status"] == "installed"
            assert "policyRuntime" in cursor_payload
            assert "policyRuntime" in factory_payload
            assert "policyRuntime" in codex_payload
            assert "policyRuntime" in claude_payload
            assert "policy-federation runtime start" in codex_toml
            assert (home / ".cursor" / "bin" / "cursor_exec_guard.sh").exists()
            assert (home / ".factory" / "bin" / "factory_exec_guard.sh").exists()
            assert (home / ".codex" / "bin" / "codex_exec_guard.sh").exists()
            assert (home / ".claude" / "bin" / "claude_pretool_guard.sh").exists()
            assert (home / ".local" / "bin" / "codex").exists()
            assert (home / ".local" / "bin" / "claude").exists()
            assert (home / ".local" / "bin" / "cursor.policy-federation.real").exists()
            pretool_commands = [
                hook["hooks"][0]["command"]
                for hook in claude_payload["hooks"]["PreToolUse"]
                if hook["hooks"]
            ]
            assert existing_pretool_command in pretool_commands
            assert '"$HOME/.claude/bin/claude_pretool_guard.sh"' in pretool_commands
            launcher_wrapper = (home / ".local" / "bin" / "cursor").read_text(
                encoding="utf-8",
            )
            assert "agentops-policy-federation launcher wrapper" in launcher_wrapper
            for launcher_name in ("codex", "cursor", "droid", "claude"):
                launcher = (home / ".local" / "bin" / launcher_name).read_text(
                    encoding="utf-8",
                )
                assert "agentops-policy-federation launcher wrapper" in launcher
                assert "infer_repo_name_from_pwd" in launcher
                assert f'command -v "{launcher_name}"' in launcher
                assert 'export POLICY_ASK_MODE="${POLICY_ASK_MODE:-review}"' in launcher
                assert 'export POLICY_AUDIT_LOG_PATH="${POLICY_AUDIT_LOG_PATH:-$HOME/.policy-federation/audit.jsonl}"' in launcher

            for manifest_name in (
                "codex_runtime_manifest.json",
                "cursor_runtime_manifest.json",
                "factory_runtime_manifest.json",
                "claude_runtime_manifest.json",
            ):
                manifest = json.loads(
                    (REPO_ROOT / "scripts" / "runtime" / manifest_name).read_text(
                        encoding="utf-8",
                    ),
                )
                assert manifest["defaults"]["ask_mode"] == "review"

            uninstall_result = uninstall_runtime_integrations(REPO_ROOT, home)

            cursor_payload = json.loads(
                (home / ".cursor" / "cli-config.json").read_text(encoding="utf-8"),
            )
            factory_payload = json.loads(
                (home / ".factory" / "settings.json").read_text(encoding="utf-8"),
            )
            codex_payload = json.loads(
                (home / ".codex" / "config.json").read_text(encoding="utf-8"),
            )
            codex_toml = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8"),
            )

            assert uninstall_result["status"] == "uninstalled"
            assert "policyRuntime" not in cursor_payload
            assert "policyRuntime" not in factory_payload
            assert "policyRuntime" not in codex_payload
            assert "policyRuntime" not in claude_payload
            assert "policy-federation runtime start" not in codex_toml
            assert not (home / ".claude" / "bin" / "claude_pretool_guard.sh").exists()
            assert not (home / ".local" / "bin" / "codex.policy-federation.real").exists()
            assert (home / ".local" / "bin" / "cursor").read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"

    def test_install_runtime_integrations_merges_claude_hook_entry(self) -> None:
        existing_pretool_command = '"$HOME/.claude/bin/hook-dispatcher" pretool'
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            (home / ".claude").mkdir()
            (home / ".claude" / "settings.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": (
                                        "Bash|Write|Edit|MultiEdit|NotebookEdit"
                                    ),
                                    "hooks": [
                                        {
                                            "type": "permission",
                                            "permission": "file-write",
                                        },
                                        {
                                            "type": "command",
                                            "command": existing_pretool_command,
                                        },
                                    ],
                                },
                            ],
                        },
                    },
                ),
                encoding="utf-8",
            )
            (home / ".cursor").mkdir()
            (home / ".factory").mkdir()
            (home / ".codex").mkdir()
            (home / ".local" / "bin").mkdir(parents=True)

            install_runtime_integrations(
                REPO_ROOT,
                home,
            )
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8"),
            )
            pre_tool_use = claude_payload["hooks"]["PreToolUse"]
            matcher = "Bash|Write|Edit|MultiEdit|NotebookEdit"
            bash_entries = [
                entry for entry in pre_tool_use if entry.get("matcher") == matcher
            ]
            assert len(bash_entries) == 1, f"expected managed matcher entry for {matcher}"
            bash_entry = bash_entries[0]
            hook_commands = {
                hook["command"] for hook in bash_entry["hooks"] if "command" in hook
            }
            hook_types = {hook["type"] for hook in bash_entry["hooks"]}
            assert existing_pretool_command in hook_commands
            assert "permission" in hook_types
            assert '"$HOME/.claude/bin/claude_pretool_guard.sh"' in hook_commands

            uninstall_runtime_integrations(REPO_ROOT, home)
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8"),
            )
            pre_tool_use = claude_payload["hooks"]["PreToolUse"]
            bash_entries = [
                entry for entry in pre_tool_use if entry.get("matcher") == matcher
            ]
            assert len(bash_entries) == 1, f"expected matcher entry for {matcher} to remain"
            bash_entry = bash_entries[0]
            remaining_commands = [
                hook.get("command")
                for hook in bash_entry.get("hooks", [])
                if hook.get("command") is not None
            ]
            assert '"$HOME/.claude/bin/claude_pretool_guard.sh"' not in remaining_commands
            assert '"$HOME/.claude/bin/hook-dispatcher" pretool' in remaining_commands


if __name__ == "__main__":
    unittest.main()

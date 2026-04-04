from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import REPO_ROOT

from policy_federation.constants import DEFAULT_REVIEW_MODEL
from policy_federation.integrations import (
    install_runtime_integrations,
    uninstall_runtime_integrations,
)


class RuntimeIntegrationsTest(unittest.TestCase):
    def test_install_runtime_integrations_patches_home_configs(self) -> None:
        existing_pretool_command = "\"$HOME/.claude/bin/hook-dispatcher\" pretool"
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            (home / ".cursor").mkdir()
            (home / ".factory").mkdir()
            (home / ".codex").mkdir()
            (home / ".claude").mkdir()
            (home / ".local" / "bin").mkdir(parents=True)
            (home / ".local" / "share" / "uv" / "tools" / "thegent" / "bin").mkdir(parents=True)
            (home / ".cursor" / "cli-config.json").write_text(
                json.dumps({"permissions": {"allow": [], "deny": []}, "version": 1}),
                encoding="utf-8",
            )
            (home / ".factory" / "settings.json").write_text(
                json.dumps({"commandAllowlist": [], "commandDenylist": []}),
                encoding="utf-8",
            )
            (home / ".codex" / "config.json").write_text(json.dumps({}), encoding="utf-8")
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
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            (home / ".local" / "bin" / "cursor").write_text(
                "#!/bin/sh\nexit 0\n",
                encoding="utf-8",
            )
            (home / ".local" / "bin" / "cursor").chmod(0o755)
            droid_binary = (
                home
                / ".local"
                / "share"
                / "uv"
                / "tools"
                / "thegent"
                / "bin"
                / "droid"
            )
            droid_binary.write_text(
                "#!/bin/sh\nexit 0\n",
                encoding="utf-8",
            )
            droid_binary.chmod(0o755)

            result = install_runtime_integrations(REPO_ROOT, home)

            cursor_payload = json.loads(
                (home / ".cursor" / "cli-config.json").read_text(encoding="utf-8")
            )
            factory_payload = json.loads(
                (home / ".factory" / "settings.json").read_text(encoding="utf-8")
            )
            codex_payload = json.loads(
                (home / ".codex" / "config.json").read_text(encoding="utf-8")
            )
            codex_toml = (home / ".codex" / "config.toml").read_text(
                encoding="utf-8"
            )
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8")
            )

            self.assertEqual(result["status"], "installed")
            self.assertIn("policyRuntime", cursor_payload)
            self.assertIn("policyRuntime", factory_payload)
            self.assertIn("policyRuntime", codex_payload)
            self.assertIn("policyRuntime", claude_payload)
            self.assertIn("policy-federation runtime start", codex_toml)
            self.assertTrue((home / ".cursor" / "bin" / "cursor_exec_guard.sh").exists())
            self.assertTrue((home / ".factory" / "bin" / "factory_exec_guard.sh").exists())
            self.assertTrue((home / ".codex" / "bin" / "codex_exec_guard.sh").exists())
            self.assertTrue((home / ".claude" / "bin" / "claude_pretool_guard.sh").exists())
            self.assertTrue((home / ".local" / "bin" / "codex").exists())
            self.assertTrue((home / ".local" / "bin" / "claude").exists())
            self.assertTrue((home / ".local" / "bin" / "cursor.policy-federation.real").exists())
            pretool_commands = [
                hook["hooks"][0]["command"]
                for hook in claude_payload["hooks"]["PreToolUse"]
                if hook["hooks"]
            ]
            self.assertIn(existing_pretool_command, pretool_commands)
            self.assertIn("\"$HOME/.claude/bin/claude_pretool_guard.sh\"", pretool_commands)
            launcher_wrapper = (home / ".local" / "bin" / "cursor").read_text(encoding="utf-8")
            self.assertIn("agentops-policy-federation launcher wrapper", launcher_wrapper)
            for launcher_name in ("codex", "cursor", "droid", "claude"):
                launcher = (home / ".local" / "bin" / launcher_name).read_text(encoding="utf-8")
                self.assertIn("agentops-policy-federation launcher wrapper", launcher)
                self.assertIn("infer_repo_name_from_pwd", launcher)
                self.assertIn(f'command -v "{launcher_name}"', launcher)
                self.assertIn('export POLICY_ASK_MODE="${POLICY_ASK_MODE:-review}"', launcher)
                self.assertIn(
                    'export POLICY_AUDIT_LOG_PATH="${POLICY_AUDIT_LOG_PATH:-$HOME/.policy-federation/audit.jsonl}"',
                    launcher,
                )

            for manifest_name in (
                "codex_runtime_manifest.json",
                "cursor_runtime_manifest.json",
                "factory_runtime_manifest.json",
                "claude_runtime_manifest.json",
            ):
                manifest = json.loads((REPO_ROOT / "scripts" / "runtime" / manifest_name).read_text(encoding="utf-8"))
                self.assertEqual(manifest["defaults"]["ask_mode"], "review")

            uninstall_result = uninstall_runtime_integrations(REPO_ROOT, home)

            cursor_payload = json.loads(
                (home / ".cursor" / "cli-config.json").read_text(encoding="utf-8")
            )
            factory_payload = json.loads(
                (home / ".factory" / "settings.json").read_text(encoding="utf-8")
            )
            codex_payload = json.loads(
                (home / ".codex" / "config.json").read_text(encoding="utf-8")
            )
            codex_toml = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8")
            )

            self.assertEqual(uninstall_result["status"], "uninstalled")
            self.assertNotIn("policyRuntime", cursor_payload)
            self.assertNotIn("policyRuntime", factory_payload)
            self.assertNotIn("policyRuntime", codex_payload)
            self.assertNotIn("policyRuntime", claude_payload)
            self.assertNotIn("policy-federation runtime start", codex_toml)
            self.assertFalse((home / ".claude" / "bin" / "claude_pretool_guard.sh").exists())
            self.assertFalse((home / ".local" / "bin" / "codex.policy-federation.real").exists())
            self.assertEqual(
                (home / ".local" / "bin" / "cursor").read_text(encoding="utf-8"),
                "#!/bin/sh\nexit 0\n",
            )

    def test_install_runtime_integrations_merges_claude_hook_entry(self) -> None:
        existing_pretool_command = "\"$HOME/.claude/bin/hook-dispatcher\" pretool"
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
                                        {"type": "permission", "permission": "file-write"},
                                        {
                                            "type": "command",
                                            "command": existing_pretool_command,
                                        },
                                    ],
                                }
                            ]
                        }
                    }
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
                (home / ".claude" / "settings.json").read_text(encoding="utf-8")
            )
            pre_tool_use = claude_payload["hooks"]["PreToolUse"]
            matcher = "Bash|Write|Edit|MultiEdit|NotebookEdit"
            bash_entries = [
                entry
                for entry in pre_tool_use
                if entry.get("matcher") == matcher
            ]
            self.assertEqual(len(bash_entries), 1, f"expected managed matcher entry for {matcher}")
            bash_entry = bash_entries[0]
            hook_commands = {
                hook["command"]
                for hook in bash_entry["hooks"]
                if "command" in hook
            }
            hook_types = {hook["type"] for hook in bash_entry["hooks"]}
            self.assertIn(
                existing_pretool_command,
                hook_commands,
            )
            self.assertIn("permission", hook_types)
            self.assertIn(
                "\"$HOME/.claude/bin/claude_pretool_guard.sh\"",
                hook_commands,
            )

            uninstall_runtime_integrations(REPO_ROOT, home)
            claude_payload = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8")
            )
            pre_tool_use = claude_payload["hooks"]["PreToolUse"]
            bash_entries = [
                entry
                for entry in pre_tool_use
                if entry.get("matcher") == matcher
            ]
            self.assertEqual(len(bash_entries), 1, f"expected matcher entry for {matcher} to remain")
            bash_entry = bash_entries[0]
            remaining_commands = [
                hook.get("command")
                for hook in bash_entry.get("hooks", [])
                if hook.get("command") is not None
            ]
            self.assertNotIn(
                "\"$HOME/.claude/bin/claude_pretool_guard.sh\"",
                remaining_commands,
            )
            self.assertIn(
                "\"$HOME/.claude/bin/hook-dispatcher\" pretool",
                remaining_commands,
            )


if __name__ == "__main__":
    unittest.main()

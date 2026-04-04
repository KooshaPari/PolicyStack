from __future__ import annotations

import unittest

from support import REPO_ROOT

from policy_federation.compiler import compile_target
from policy_federation.resolver import resolve


class CompilerTest(unittest.TestCase):
    def test_codex_compile_surfaces_conditional_rules_as_shims(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("codex", resolved)
        self.assertIn(
            "git commit --no-verify*",
            compiled["native_config"]["permissions"]["deny_prefixes"],
        )
        self.assertIn("git commit*", compiled["native_config"]["permissions"]["deny_prefixes"])
        shim_ids = {rule["id"] for rule in compiled["shim_rules"]}
        self.assertIn("thegent-allow-git-write-in-worktrees", shim_ids)
        self.assertIn("thegent-deny-write-outside-worktrees", shim_ids)
        self.assertIn("devops-ask-network-egress", shim_ids)

    def test_codex_compile_surfaces_host_safe_allow_prefixes(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("codex", resolved)
        permissions = compiled["native_config"]["permissions"]
        self.assertIn("ps*", permissions["allow_prefixes"])
        self.assertIn(
            "mkdir -p /Users/kooshapari/CodeProjects/Phenotype/repos/*",
            permissions["allow_prefixes"],
        )
        self.assertIn("go clean -cache*", permissions["allow_prefixes"])
        self.assertIn(
            "rm -rf ~/Library/Caches/Homebrew/downloads/*",
            permissions["allow_prefixes"],
        )
        self.assertIn("timeout * bun test*", permissions["allow_prefixes"])
        self.assertIn("timeout * pytest*", permissions["allow_prefixes"])
        self.assertIn("timeout * python -m pytest*", permissions["allow_prefixes"])
        self.assertIn("timeout * python3 -m pytest*", permissions["allow_prefixes"])
        self.assertIn(
            "mv /Users/kooshapari/CodeProjects/Phenotype/repos/* /Users/kooshapari/CodeProjects/Phenotype/repos/.archive/*",
            permissions["allow_prefixes"],
        )
        self.assertIn(
            "rm -rf /Users/kooshapari/CodeProjects/Phenotype/repos/*",
            permissions["deny_prefixes"],
        )
        self.assertIn("git symbolic-ref*", permissions["allow_prefixes"])
        self.assertIn("git worktree add*", permissions["allow_prefixes"])
        self.assertIn("diff*", permissions["allow_prefixes"])
        self.assertIn("command -v *", permissions["allow_prefixes"])
        self.assertIn("basename *", permissions["allow_prefixes"])
        self.assertIn("pwd", permissions["allow_prefixes"])
        self.assertIn("readlink -f *", permissions["allow_prefixes"])
        self.assertIn("realpath *", permissions["allow_prefixes"])

    def test_cursor_compile_includes_runtime_wrappers(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="cursor-agent",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("cursor-agent", resolved)
        wrapper = compiled["native_config"]["runtime_wrapper"]
        self.assertEqual(wrapper["exec"], "./scripts/runtime/cursor_exec_guard.sh")
        self.assertEqual(wrapper["write_check"], "./scripts/runtime/cursor_write_guard.sh")

    def test_factory_compile_includes_runtime_wrappers(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="factory-droid",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("factory-droid", resolved)
        wrapper = compiled["native_config"]["runtime_wrapper"]
        self.assertEqual(wrapper["exec"], "./scripts/runtime/factory_exec_guard.sh")
        self.assertEqual(wrapper["network_check"], "./scripts/runtime/factory_network_guard.sh")
        self.assertEqual(compiled["native_config"]["approvalMode"], "review")

    def test_claude_compile_includes_pretool_hook(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="claude-code",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("claude-code", resolved)
        wrapper = compiled["native_config"]["runtime_wrapper"]
        self.assertEqual(wrapper["exec"], "./scripts/runtime/claude_exec_guard.sh")
        self.assertEqual(wrapper["pretool_hook"], "./scripts/runtime/claude_pretool_hook.py")
        pretool = compiled["native_config"]["hooks"]["PreToolUse"][0]
        self.assertEqual(
            pretool["matcher"],
            "Bash|Write|Edit|MultiEdit|WebFetch|WebSearch|NotebookEdit",
        )

    def test_all_targets_share_parity_for_native_and_runtime_actions(self) -> None:
        resolved_payload = {
            "policy": {
                "authorization": {
                    "defaults": {},
                    "rules": [
                        {
                            "id": "test-allow-exec-native",
                            "description": "Allow unconditional native exec command.",
                            "effect": "allow",
                            "actions": ["exec"],
                            "priority": 100,
                            "match": {"command_patterns": ["echo*"]},
                        },
                        {
                            "id": "test-deny-write-any",
                            "description": "Deny write outside runtime wrapper support.",
                            "effect": "deny",
                            "actions": ["write"],
                            "priority": 50,
                            "match": {"target_path_patterns": ["*"]},
                        },
                        {
                            "id": "test-ask-network",
                            "description": "Ask on network usage.",
                            "effect": "ask",
                            "actions": ["network"],
                            "priority": 90,
                            "match": {"command_patterns": ["curl*"]},
                        },
                        {
                            "id": "test-deny-shutdown",
                            "description": "Guardrail shutdown action.",
                            "effect": "deny",
                            "actions": ["shutdown"],
                            "priority": 80,
                            "match": {"command_patterns": ["shutdown*"]},
                        },
                        {
                            "id": "test-allow-exec-conditional",
                            "description": "Conditional exec rule requiring runtime.",
                            "effect": "allow",
                            "actions": ["exec"],
                            "priority": 70,
                            "match": {
                                "cwd_patterns": ["/tmp/*"],
                                "command_patterns": ["git status*"],
                            },
                        },
                        {
                            "id": "test-allow-exec-no-command",
                            "description": "Fallback to runtime check when no command pattern.",
                            "effect": "allow",
                            "actions": ["exec"],
                            "priority": 60,
                            "match": {},
                        },
                        {
                            "id": "test-ask-exec",
                            "description": "Ask for npm publish.",
                            "effect": "ask",
                            "actions": ["exec"],
                            "priority": 75,
                            "match": {"command_patterns": ["npm publish*"]},
                        },
                    ],
                }
            },
            "policy_hash": "unit-matrix",
            "scope_chain": [],
        }

        target_wrappers = {
            "codex": "./scripts/runtime/codex_exec_guard.sh",
            "cursor-agent": "./scripts/runtime/cursor_exec_guard.sh",
            "factory-droid": "./scripts/runtime/factory_exec_guard.sh",
            "claude-code": "./scripts/runtime/claude_exec_guard.sh",
        }

        expected_runtime_only_flags = {
            "test-deny-write-any": ["write"],
            "test-ask-network": ["network"],
            "test-deny-shutdown": ["shutdown"],
            "test-allow-exec-conditional": ["exec"],
            "test-allow-exec-no-command": ["exec"],
        }
        for target, wrapper_path in target_wrappers.items():
            compiled = compile_target(target, resolved_payload)
            self.assertEqual(compiled["native_config"]["runtime_wrapper"]["exec"], wrapper_path)

            shim_ids = {rule["id"] for rule in compiled["shim_rules"]}
            self.assertIn("test-deny-write-any", shim_ids)
            self.assertIn("test-ask-network", shim_ids)
            self.assertIn("test-deny-shutdown", shim_ids)
            self.assertIn("test-allow-exec-conditional", shim_ids)
            self.assertIn("test-allow-exec-no-command", shim_ids)

            shim_index = {rule["id"]: rule for rule in compiled["shim_rules"]}
            for rule_id, actions in expected_runtime_only_flags.items():
                self.assertIn(rule_id, shim_index)
                rule = shim_index[rule_id]
                self.assertIn("actions", rule)
                self.assertEqual(rule["actions"], actions)
                self.assertTrue(
                    rule["requires_runtime_check"],
                    f"Expected runtime-check marker for {rule_id}",
                )
            if target == "factory-droid":
                factory_ask_shim = shim_index["ask::npm publish*"]
                self.assertIn("requires_runtime_check", factory_ask_shim)
                self.assertEqual(factory_ask_shim["actions"], ["ask"])

            if target == "codex":
                permissions = compiled["native_config"]["permissions"]
                self.assertIn("echo*", permissions["allow_prefixes"])
                self.assertIn("npm publish*", permissions["ask_prefixes"])
            elif target == "factory-droid":
                self.assertIn("echo*", compiled["native_config"]["commandAllowlist"])
                self.assertIn("ask::npm publish*", shim_ids)
            elif target == "claude-code":
                permissions = compiled["native_config"]["permissions"]
                self.assertIn("Bash(echo*)", permissions["allow"])
            else:
                permissions = compiled["native_config"]["permissions"]
                self.assertIn("Shell(echo*)", permissions["allow"])


if __name__ == "__main__":
    unittest.main()

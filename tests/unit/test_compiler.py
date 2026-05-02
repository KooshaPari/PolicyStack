from __future__ import annotations

import unittest

from policy_federation.compiler import compile_target
from policy_federation.resolver import resolve
from support import REPO_ROOT


class CompilerTest(unittest.TestCase):
    def test_codex_compile_surfaces_conditional_rules_as_shims(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("codex", resolved)
        assert "git commit --no-verify*" in compiled["native_config"]["permissions"]["deny_prefixes"]
        assert "git commit*" in compiled["native_config"]["permissions"]["deny_prefixes"]
        shim_ids = {rule["id"] for rule in compiled["shim_rules"]}
        assert "thegent-allow-git-write-in-worktrees" in shim_ids
        assert "thegent-deny-write-outside-worktrees" in shim_ids
        assert "devops-ask-network-egress" in shim_ids

    def test_codex_compile_surfaces_host_safe_allow_prefixes(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("codex", resolved)
        permissions = compiled["native_config"]["permissions"]
        assert "ps*" in permissions["allow_prefixes"]
        assert "mkdir -p /Users/kooshapari/CodeProjects/Phenotype/repos/*" in permissions["allow_prefixes"]
        assert "go clean -cache*" in permissions["allow_prefixes"]
        assert "rm -rf ~/Library/Caches/Homebrew/downloads/*" in permissions["allow_prefixes"]
        assert "timeout * bun test*" in permissions["allow_prefixes"]
        assert "timeout * pytest*" in permissions["allow_prefixes"]
        assert "timeout * python -m pytest*" in permissions["allow_prefixes"]
        assert "timeout * python3 -m pytest*" in permissions["allow_prefixes"]
        assert "mv /Users/kooshapari/CodeProjects/Phenotype/repos/* /Users/kooshapari/CodeProjects/Phenotype/repos/.archive/*" in permissions["allow_prefixes"]
        assert "rm -rf /Users/kooshapari/CodeProjects/Phenotype/repos/*" in permissions["deny_prefixes"]
        assert "git symbolic-ref*" in permissions["allow_prefixes"]
        assert "git worktree add*" in permissions["allow_prefixes"]
        assert "diff*" in permissions["allow_prefixes"]
        assert "command -v *" in permissions["allow_prefixes"]
        assert "basename *" in permissions["allow_prefixes"]
        assert "pwd" in permissions["allow_prefixes"]
        assert "readlink -f *" in permissions["allow_prefixes"]
        assert "realpath *" in permissions["allow_prefixes"]

    def test_cursor_compile_includes_runtime_wrappers(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="cursor-agent",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("cursor-agent", resolved)
        wrapper = compiled["native_config"]["runtime_wrapper"]
        assert wrapper["exec"] == "./scripts/runtime/cursor_exec_guard.sh"
        assert wrapper["write_check"] == "./scripts/runtime/cursor_write_guard.sh"

    def test_factory_compile_includes_runtime_wrappers(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="factory-droid",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("factory-droid", resolved)
        wrapper = compiled["native_config"]["runtime_wrapper"]
        assert wrapper["exec"] == "./scripts/runtime/factory_exec_guard.sh"
        assert wrapper["network_check"] == "./scripts/runtime/factory_network_guard.sh"
        assert compiled["native_config"]["approvalMode"] == "review"

    def test_claude_compile_includes_pretool_hook(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="claude-code",
            repo="thegent",
            task_domain="devops",
        )
        compiled = compile_target("claude-code", resolved)
        wrapper = compiled["native_config"]["runtime_wrapper"]
        assert wrapper["exec"] == "./scripts/runtime/claude_exec_guard.sh"
        assert wrapper["pretool_hook"] == "./scripts/runtime/claude_pretool_hook.py"
        pretool = compiled["native_config"]["hooks"]["PreToolUse"][0]
        assert pretool["matcher"] == "Bash|Write|Edit|MultiEdit|WebFetch|WebSearch|NotebookEdit"

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
                },
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
            assert compiled["native_config"]["runtime_wrapper"]["exec"] == wrapper_path

            shim_ids = {rule["id"] for rule in compiled["shim_rules"]}
            assert "test-deny-write-any" in shim_ids
            assert "test-ask-network" in shim_ids
            assert "test-deny-shutdown" in shim_ids
            assert "test-allow-exec-conditional" in shim_ids
            assert "test-allow-exec-no-command" in shim_ids

            shim_index = {rule["id"]: rule for rule in compiled["shim_rules"]}
            for rule_id, actions in expected_runtime_only_flags.items():
                assert rule_id in shim_index
                rule = shim_index[rule_id]
                assert "actions" in rule
                assert rule["actions"] == actions
                assert rule["requires_runtime_check"], f"Expected runtime-check marker for {rule_id}"
            if target == "factory-droid":
                factory_ask_shim = shim_index["ask::npm publish*"]
                assert "requires_runtime_check" in factory_ask_shim
                assert factory_ask_shim["actions"] == ["ask"]

            if target == "codex":
                permissions = compiled["native_config"]["permissions"]
                assert "echo*" in permissions["allow_prefixes"]
                assert "npm publish*" in permissions["ask_prefixes"]
            elif target == "factory-droid":
                assert "echo*" in compiled["native_config"]["commandAllowlist"]
                assert "ask::npm publish*" in shim_ids
            elif target == "claude-code":
                permissions = compiled["native_config"]["permissions"]
                assert "Bash(echo*)" in permissions["allow"]
            else:
                permissions = compiled["native_config"]["permissions"]
                assert "Shell(echo*)" in permissions["allow"]


if __name__ == "__main__":
    unittest.main()

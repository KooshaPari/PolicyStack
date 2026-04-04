"""Harness target compilation for resolved authorization policy."""
from __future__ import annotations

from .authorization import normalize_authorization_rules


SUPPORTED_TARGETS = {"claude-code", "codex", "factory-droid", "cursor-agent"}


def compile_target(target: str, resolved_payload: dict) -> dict:
    """Compile a resolved policy payload into a target-specific config plan."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")

    policy = resolved_payload["policy"]
    defaults, rules = normalize_authorization_rules(policy)

    native_allow: list[str] = []
    native_deny: list[str] = []
    native_ask: list[str] = []
    shim_rules: list[dict] = []
    ignored_rules: list[dict] = []

    def _shim_rule(rule: dict, *, reason: str, command_patterns: list[str] | None = None) -> dict:
        payload = dict(rule)
        payload["reason"] = reason
        payload["requires_runtime_check"] = True
        if command_patterns is not None:
            payload["command_patterns"] = command_patterns
        return payload

    for rule in rules:
        if "exec" not in rule.actions and "*" not in rule.actions:
            shim_rules.append(
                _shim_rule(
                    {
                        "id": rule.rule_id,
                        "actions": sorted(list(rule.actions)),
                        "effect": rule.effect,
                        "priority": rule.priority,
                        "conditions": {
                            "cwd_patterns": list(rule.cwd_patterns),
                            "actor_patterns": list(rule.actor_patterns),
                            "target_path_patterns": list(rule.target_path_patterns),
                        },
                    },
                    reason="runtime_only_action_requires_interceptor",
                    command_patterns=list(rule.command_patterns),
                )
            )
            continue

        if not rule.command_patterns:
            shim_rules.append(
                _shim_rule(
                    {
                        "id": rule.rule_id,
                        "actions": sorted(list(rule.actions)),
                        "effect": rule.effect,
                    },
                    reason="missing_command_patterns",
                )
            )
            continue

        if rule.has_conditions:
            shim_rules.append(
                _shim_rule(
                    {
                        "id": rule.rule_id,
                        "actions": sorted(list(rule.actions)),
                        "effect": rule.effect,
                        "priority": rule.priority,
                        "conditions": {
                            "cwd_patterns": list(rule.cwd_patterns),
                            "actor_patterns": list(rule.actor_patterns),
                            "target_path_patterns": list(rule.target_path_patterns),
                        },
                    },
                    reason="conditional_rule_requires_runtime_interceptor",
                    command_patterns=list(rule.command_patterns),
                )
            )
            continue

        if rule.effect == "allow":
            native_allow.extend(rule.command_patterns)
        elif rule.effect == "deny":
            native_deny.extend(rule.command_patterns)
        else:
            native_ask.extend(rule.command_patterns)

    runtime = policy.get("runtime") or {}
    approvals = policy.get("approvals") or {}

    if target == "codex":
        native_config = {
            "approval_policy": "on-request" if defaults.get("exec", "ask") == "ask" else "never",
            "sandbox_mode": runtime.get("sandbox", "required"),
            "permissions": {
                "allow_prefixes": sorted(dict.fromkeys(native_allow)),
                "deny_prefixes": sorted(dict.fromkeys(native_deny)),
                "ask_prefixes": sorted(dict.fromkeys(native_ask)),
            },
            "runtime_wrapper": {
                "exec": "./scripts/runtime/codex_exec_guard.sh",
                "write_check": "python -m policy_federation.cli write-check",
                "network_check": "python -m policy_federation.cli network-check",
            },
        }
    elif target == "factory-droid":
        native_config = {
            "commandAllowlist": sorted(dict.fromkeys(native_allow)),
            "commandDenylist": sorted(dict.fromkeys(native_deny)),
            "approvalMode": approvals.get("command_ask_mode", defaults.get("exec", "ask")),
            "runtime_wrapper": {
                "exec": "./scripts/runtime/factory_exec_guard.sh",
                "write_check": "./scripts/runtime/factory_write_guard.sh",
                "network_check": "./scripts/runtime/factory_network_guard.sh",
            },
        }
        if native_ask:
            shim_rules.extend(
                _shim_rule(
                    {
                        "id": f"ask::{pattern}",
                        "effect": "ask",
                        "actions": ["ask"],
                        "command_patterns": [pattern],
                    },
                    reason="factory_native_ask_not_supported",
                )
                for pattern in native_ask
            )
    elif target == "claude-code":
        native_config = {
            "permissions": {
                "allow": [f"Bash({pattern})" for pattern in sorted(dict.fromkeys(native_allow))],
                "deny": [f"Bash({pattern})" for pattern in sorted(dict.fromkeys(native_deny))],
                "ask": [f"Bash({pattern})" for pattern in sorted(dict.fromkeys(native_ask))],
            },
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash|Write|Edit|MultiEdit|WebFetch|WebSearch|NotebookEdit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "\"$HOME/.claude/bin/claude_pretool_guard.sh\"",
                            }
                        ],
                    }
                ]
            },
            "runtime_wrapper": {
                "exec": "./scripts/runtime/claude_exec_guard.sh",
                "write_check": "./scripts/runtime/claude_write_guard.sh",
                "network_check": "./scripts/runtime/claude_network_guard.sh",
                "pretool_hook": "./scripts/runtime/claude_pretool_hook.py",
            },
        }
    else:
        native_config = {
            "permissions": {
                "allow": [f"Shell({pattern})" for pattern in sorted(dict.fromkeys(native_allow))],
                "deny": [f"Shell({pattern})" for pattern in sorted(dict.fromkeys(native_deny))],
                "ask": [f"Shell({pattern})" for pattern in sorted(dict.fromkeys(native_ask))],
            },
            "runtime_wrapper": {
                "exec": "./scripts/runtime/cursor_exec_guard.sh",
                "write_check": "./scripts/runtime/cursor_write_guard.sh",
                "network_check": "./scripts/runtime/cursor_network_guard.sh",
            },
        }

    return {
        "target": target,
        "defaults": defaults,
        "native_config": native_config,
        "shim_rules": shim_rules,
        "ignored_rules": ignored_rules,
        "policy_hash": resolved_payload["policy_hash"],
        "scope_chain": resolved_payload["scope_chain"],
    }

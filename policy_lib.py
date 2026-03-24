#!/usr/bin/env python3
"""Shared permission policy language primitives and evaluator."""

from __future__ import annotations

import hashlib
import fnmatch
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


Decision = str
ALLOWED_ACTIONS = {"allow", "request", "deny"}
ALLOWED_MATCHERS = {"exact", "glob", "prefix"}


def _safe_split(command: str) -> list[str]:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    return [part.strip() for part in parts if part.strip()]


def _normalized_command(command: str) -> str:
    return " ".join(_safe_split(command))


def _run_git(cwd: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "git command failed")
    return process.stdout.strip()


def _condition_git_is_worktree(cwd: Path) -> tuple[bool, str]:
    try:
        value = _run_git(cwd, "rev-parse", "--is-inside-work-tree")
    except RuntimeError as exc:
        return False, f"git_is_worktree: {exc}"
    return value == "true", "git_is_worktree"


def _condition_git_clean(cwd: Path) -> tuple[bool, str]:
    try:
        output = _run_git(cwd, "status", "--porcelain")
    except RuntimeError as exc:
        return False, f"git_clean_worktree: {exc}"
    return output == "", "git_clean_worktree"


def _condition_git_synced_to_upstream(cwd: Path) -> tuple[bool, str]:
    try:
        _run_git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    except RuntimeError as exc:
        return False, f"git_synced_to_upstream: no upstream ({exc})"

    try:
        counts = _run_git(
            cwd,
            "rev-list",
            "--left-right",
            "--count",
            "@{u}...HEAD",
        )
    except RuntimeError as exc:
        return False, f"git_synced_to_upstream: unable to compare upstream ({exc})"

    parts = counts.split()
    if len(parts) != 2:
        return False, f"git_synced_to_upstream: unexpected counts {counts!r}"

    behind, ahead = parts[0], parts[1]
    if behind != "0" or ahead != "0":
        return (
            False,
            f"git_synced_to_upstream: behind={behind}, ahead={ahead}",
        )
    return True, "git_synced_to_upstream"


CONDITION_EVALUATORS = {
    "git_is_worktree": _condition_git_is_worktree,
    "git_clean_worktree": _condition_git_clean,
    "git_synced_to_upstream": _condition_git_synced_to_upstream,
}


@dataclass(frozen=True)
class Condition:
    name: str
    required: bool = True
    explicit: bool = False

    def export(self) -> str | dict[str, Any]:
        if self.required:
            if self.explicit:
                return {"name": self.name, "required": True}
            return self.name
        return {"name": self.name, "required": False}

    def evaluate(self, cwd: Path) -> tuple[bool, str]:
        evaluator = CONDITION_EVALUATORS.get(self.name)
        if evaluator is None:
            return False, f"unsupported_condition:{self.name}"
        return evaluator(cwd)


@dataclass(frozen=True)
class ConditionGroup:
    mode: str = "all"
    items: tuple[Condition | ConditionGroup, ...] = field(default_factory=tuple)

    @staticmethod
    def _is_required(condition: Condition | ConditionGroup) -> bool:
        return condition.required if isinstance(condition, Condition) else True

    @staticmethod
    def _append_reason(reasons: list[str], reason: str | list[str]) -> None:
        if isinstance(reason, list):
            reasons.extend(reason)
        else:
            reasons.append(reason)

    def evaluate(self, cwd: Path) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if not self.items:
            return True, reasons

        if self.mode == "any":
            has_required = False
            pass_required = False
            pass_optional = False
            for condition in self.items:
                ok, reason = condition.evaluate(cwd)
                self._append_reason(reasons, reason)
                required = self._is_required(condition)
                if required:
                    has_required = True
                    if ok:
                        pass_required = True
                elif ok:
                    pass_optional = True

            if pass_required or (not has_required and pass_optional):
                return True, reasons
            return False, reasons

        for condition in self.items:
            ok, reason = condition.evaluate(cwd)
            self._append_reason(reasons, reason)
            if self._is_required(condition) and not ok:
                return False, reasons
        return True, reasons

    def export(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "conditions": [
                (
                    condition.export()
                    if isinstance(condition, Condition)
                    else condition.export()
                )
                for condition in self.items
            ],
        }


@dataclass(frozen=True)
class CommandRule:
    rule_id: str
    action: Decision
    pattern: str
    matcher: str = "glob"
    source: str = ""
    conditions: ConditionGroup | None = None
    on_mismatch: Decision | None = None

    def matches(self, command: str) -> bool:
        normalized = _normalized_command(command)
        pattern = self.pattern.strip()
        if not pattern:
            return False

        if self.matcher == "exact":
            return normalized == _normalized_command(pattern)
        if self.matcher == "prefix":
            return normalized.startswith(_normalized_command(pattern))
        return fnmatch.fnmatchcase(normalized, pattern)

    def evaluate(self, command: str, cwd: Path) -> Decision | None:
        if not self.matches(command):
            return None

        if not self.conditions:
            return self.action

        ok, reasons = self.conditions.evaluate(cwd)
        if ok:
            return self.action
        if self.on_mismatch:
            return self.on_mismatch
        return None

    def decision_trace(self) -> str:
        return f"{self.rule_id}::{self.action}::{self.source}"

    def export(self) -> dict[str, Any]:
        payload = {
            "rule_id": self.rule_id,
            "action": self.action,
            "source": self.source,
            "pattern": self.pattern,
            "matcher": self.matcher,
            "on_mismatch": self.on_mismatch,
        }
        if self.conditions is not None:
            payload["conditions"] = self.conditions.export()
        return payload


def _parse_condition_group(value: Any) -> ConditionGroup | None:
    if value is None:
        return None
    if isinstance(value, str):
        return ConditionGroup(items=(Condition(value, required=True, explicit=False),))
    if isinstance(value, list):
        return ConditionGroup(items=tuple(_parse_condition(v) for v in value))
    if not isinstance(value, dict):
        raise ValueError(f"unsupported condition type: {type(value).__name__}")

    if "all" in value:
        conditions = value["all"]
        if not isinstance(conditions, list):
            raise ValueError("'all' must be a list")
        return ConditionGroup(mode="all", items=tuple(_parse_condition(v) for v in conditions))

    if "any" in value:
        conditions = value["any"]
        if not isinstance(conditions, list):
            raise ValueError("'any' must be a list")
        return ConditionGroup(mode="any", items=tuple(_parse_condition(v) for v in conditions))

    if "mode" in value and "conditions" in value:
        mode = value["mode"]
        if mode not in {"all", "any"}:
            raise ValueError(f"unsupported condition mode: {mode!r}")
        conditions = value["conditions"]
        if not isinstance(conditions, list):
            raise ValueError("'conditions' must be a list when 'mode' is set")
        return ConditionGroup(mode=mode, items=tuple(_parse_condition(v) for v in conditions))

    return ConditionGroup(items=(_parse_condition(value),))


def _parse_condition(value: Any) -> Condition | ConditionGroup:
    required = True
    explicit = False
    if isinstance(value, str):
        name = value
    elif isinstance(value, list) or (
        isinstance(value, dict) and ("all" in value or "any" in value or "mode" in value)
    ):
        return _parse_condition_group(value)
    elif isinstance(value, dict) and "name" not in value:
        raise ValueError(f"condition dict must include name: {value!r}")
    elif isinstance(value, dict):
        explicit = True
        name = str(value["name"])
        if "required" in value and not isinstance(value["required"], bool):
            raise ValueError(f"condition.required must be boolean: {value!r}")
        required = bool(value.get("required", True))
    else:
        raise ValueError(f"unsupported condition type: {type(value).__name__}")
    if name not in CONDITION_EVALUATORS:
        raise ValueError(f"unsupported condition: {name}")
    return Condition(name, required=required, explicit=explicit)


def _parse_match(match: Any) -> tuple[str, str]:
    if isinstance(match, str):
        if not match.strip():
            raise ValueError("match pattern must be a non-empty string")
        return "glob", match
    if match is None:
        raise ValueError("match or pattern must be a non-empty string")
    if not isinstance(match, dict) or not match:
        raise ValueError(f"invalid match block: {match!r}")
    if len(match) != 1:
        raise ValueError(f"match block must have one key: {match!r}")
    matcher, pattern = next(iter(match.items()))
    if matcher not in ALLOWED_MATCHERS:
        raise ValueError(f"unsupported matcher: {matcher}")
    if not isinstance(pattern, str):
        raise ValueError(f"matcher pattern must be string: {pattern!r}")
    if not pattern.strip():
        raise ValueError("matcher pattern must be a non-empty string")
    return matcher, pattern


def normalize_payload(payload: dict[str, Any], cwd: Path | None = None) -> list[CommandRule]:
    if not isinstance(payload, dict):
        raise ValueError("policy payload must be a mapping")

    policy = payload.get("policy", payload)
    if not isinstance(policy, dict):
        raise ValueError("'policy' must be a mapping")

    def _as_command_list(name: str) -> list[str]:
        rules = commands.get(name, [])
        if not isinstance(rules, list):
            raise ValueError(f"policy.commands.{name} must be a list")
        normalized_patterns: list[str] = []
        for idx, value in enumerate(rules):
            if not isinstance(value, str):
                raise ValueError(
                    f"policy.commands.{name}[{idx}] must be a non-empty string"
                )
            if not value.strip():
                raise ValueError(
                    f"policy.commands.{name}[{idx}] must be a non-empty string"
                )
            normalized_patterns.append(value)
        return normalized_patterns

    rules: list[CommandRule] = []

    commands = policy.get("commands", {})
    if not isinstance(commands, dict):
        raise ValueError("policy.commands must be a map")

    allow_rules = _as_command_list("allow")
    deny_rules = _as_command_list("deny")
    require_rules = _as_command_list("require")

    for pattern in deny_rules:
        rules.append(
            CommandRule(
                rule_id=f"static-deny:{hashlib.sha1(pattern.encode()).hexdigest()[:8]}",
                action="deny",
                pattern=str(pattern),
                matcher="glob",
                source="commands",
            )
        )

    for pattern in require_rules:
        rules.append(
            CommandRule(
                rule_id=f"static-require:{hashlib.sha1(pattern.encode()).hexdigest()[:8]}",
                action="request",
                pattern=str(pattern),
                matcher="glob",
                source="commands",
            )
        )

    for pattern in allow_rules:
        rules.append(
            CommandRule(
                rule_id=f"static-allow:{hashlib.sha1(pattern.encode()).hexdigest()[:8]}",
                action="allow",
                pattern=str(pattern),
                matcher="glob",
                source="commands",
            )
        )

    command_rules = policy.get("command_rules", [])
    if not isinstance(command_rules, list):
        raise ValueError("policy.command_rules must be a list")

    for idx, entry in enumerate(command_rules):
        if not isinstance(entry, dict):
            raise ValueError(f"command_rule[{idx}] must be a map")
        rule_id = str(entry.get("id") or f"cmd-rule-{idx}")
        action = entry.get("action")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"command_rule[{idx}] invalid action: {action}")
        match = entry.get("match")
        if match is None and "pattern" in entry:
            match = entry.get("pattern")
        matcher, pattern = _parse_match(match)
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError(f"command_rule[{idx}] pattern must be a non-empty string")
        conditions = _parse_condition_group(entry.get("conditions"))
        on_mismatch = entry.get("on_mismatch")
        if on_mismatch is not None and on_mismatch not in ALLOWED_ACTIONS:
            raise ValueError(
                f"command_rule[{idx}] invalid on_mismatch action: {on_mismatch}"
            )
        rules.append(
            CommandRule(
                rule_id=rule_id,
                action=str(action),
                pattern=pattern,
                matcher=matcher,
                source="command_rules",
                conditions=conditions,
                on_mismatch=on_mismatch,
            )
        )

    return rules


def evaluate_policy(
    payload: dict[str, Any], command: str, cwd: Path | None = None
) -> tuple[Decision, str, CommandRule | None]:
    cwd = cwd or Path.cwd()
    rules = normalize_payload(payload, cwd)
    reasons = {"deny": [], "allow": [], "request": []}
    matches: list[tuple[Decision, CommandRule, str]] = []

    for rule in rules:
        decision = rule.evaluate(command, cwd=cwd)
        if decision is None:
            continue
        reason = rule.decision_trace()
        reasons[decision].append(reason)
        matches.append((decision, rule, reason))

    for decision in ("deny", "request", "allow"):
        for current, rule, reason in matches:
            if current == decision:
                return current, reason, rule

    return "allow", "no_policy_match", None

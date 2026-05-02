"""Authorization rule normalization and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch

ALLOWED_EFFECTS = {"allow", "deny", "ask"}
EFFECT_RANK = {"allow": 0, "ask": 1, "deny": 2}


@dataclass(frozen=True)
class AuthorizationRule:
    """Normalized authorization rule."""

    rule_id: str
    effect: str
    actions: tuple[str, ...]
    priority: int
    description: str
    command_patterns: tuple[str, ...]
    cwd_patterns: tuple[str, ...]
    actor_patterns: tuple[str, ...]
    target_path_patterns: tuple[str, ...]

    @property
    def has_conditions(self) -> bool:
        return bool(
            self.cwd_patterns or self.actor_patterns or self.target_path_patterns,
        )


def normalize_authorization_rules(
    policy: dict,
) -> tuple[dict[str, str], list[AuthorizationRule]]:
    """Extract and normalize authorization defaults and rules from a merged policy."""
    authorization = policy.get("authorization") or {}
    defaults = dict(authorization.get("defaults") or {})
    raw_rules = authorization.get("rules") or []
    rules: list[AuthorizationRule] = []

    for _index, raw_rule in enumerate(raw_rules):
        match = raw_rule.get("match") or {}
        rules.append(
            AuthorizationRule(
                rule_id=raw_rule["id"],
                effect=raw_rule["effect"],
                actions=tuple(raw_rule["actions"]),
                priority=int(raw_rule.get("priority", 0)),
                description=raw_rule.get("description", ""),
                command_patterns=tuple(match.get("command_patterns") or ()),
                cwd_patterns=tuple(match.get("cwd_patterns") or ()),
                actor_patterns=tuple(match.get("actor_patterns") or ()),
                target_path_patterns=tuple(match.get("target_path_patterns") or ()),
            ),
        )

    rules.sort(
        key=lambda rule: (-rule.priority, -EFFECT_RANK[rule.effect], rule.rule_id),
    )
    return defaults, rules


def validate_authorization_block(doc: dict) -> None:
    """Perform semantic validation beyond JSON Schema shape checks."""
    authorization = (doc.get("policy") or {}).get("authorization")
    if not authorization:
        return

    defaults = authorization.get("defaults") or {}
    if not isinstance(defaults, dict):
        msg = "policy.authorization.defaults must be a mapping"
        raise ValueError(msg)
    for action, effect in defaults.items():
        if not isinstance(action, str) or not action:
            msg = "policy.authorization.defaults keys must be non-empty strings"
            raise ValueError(
                msg,
            )
        if effect not in ALLOWED_EFFECTS:
            msg = f"policy.authorization.defaults[{action!r}] must be allow|deny|ask"
            raise ValueError(
                msg,
            )

    raw_rules = authorization.get("rules") or []
    if not isinstance(raw_rules, list):
        msg = "policy.authorization.rules must be a list"
        raise ValueError(msg)

    seen_rule_ids: set[str] = set()
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            msg = "policy.authorization.rules entries must be mappings"
            raise ValueError(msg)
        rule_id = raw_rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            msg = "policy.authorization.rules entries require a non-empty id"
            raise ValueError(
                msg,
            )
        if rule_id in seen_rule_ids:
            msg = f"duplicate authorization rule id: {rule_id}"
            raise ValueError(msg)
        seen_rule_ids.add(rule_id)

        effect = raw_rule.get("effect")
        if effect not in ALLOWED_EFFECTS:
            msg = f"authorization rule {rule_id} effect must be allow|deny|ask"
            raise ValueError(
                msg,
            )

        actions = raw_rule.get("actions")
        if (
            not isinstance(actions, list)
            or not actions
            or not all(isinstance(action, str) and action for action in actions)
        ):
            msg = f"authorization rule {rule_id} actions must be a non-empty string list"
            raise ValueError(
                msg,
            )

        priority = raw_rule.get("priority", 0)
        if not isinstance(priority, int):
            msg = f"authorization rule {rule_id} priority must be an integer"
            raise ValueError(
                msg,
            )

        match = raw_rule.get("match") or {}
        if match and not isinstance(match, dict):
            msg = f"authorization rule {rule_id} match must be a mapping"
            raise ValueError(msg)
        for key in (
            "command_patterns",
            "cwd_patterns",
            "actor_patterns",
            "target_path_patterns",
        ):
            values = match.get(key) or []
            if values and (
                not isinstance(values, list)
                or not all(isinstance(value, str) and value for value in values)
            ):
                msg = f"authorization rule {rule_id} {key} must be a non-empty string list"
                raise ValueError(
                    msg,
                )


def evaluate_authorization(
    policy: dict,
    *,
    action: str,
    command: str | None = None,
    cwd: str | None = None,
    actor: str | None = None,
    target_paths: list[str] | None = None,
) -> dict:
    """Evaluate an action against normalized authorization rules."""
    defaults, rules = normalize_authorization_rules(policy)
    target_paths = target_paths or []

    matched_rules: list[AuthorizationRule] = []
    for rule in rules:
        if action not in rule.actions and "*" not in rule.actions:
            continue
        if rule.command_patterns and (not command or not any(
            fnmatch(command, pattern) for pattern in rule.command_patterns
        )):
            continue
        if rule.cwd_patterns and (not cwd or not any(
            fnmatch(cwd, pattern) for pattern in rule.cwd_patterns
        )):
            continue
        if rule.actor_patterns and (not actor or not any(
            fnmatch(actor, pattern) for pattern in rule.actor_patterns
        )):
            continue
        if rule.target_path_patterns:
            if not target_paths:
                continue
            if not any(
                fnmatch(target_path, pattern)
                for target_path in target_paths
                for pattern in rule.target_path_patterns
            ):
                continue
        matched_rules.append(rule)

    if matched_rules:
        top_priority = matched_rules[0].priority
        candidates = [rule for rule in matched_rules if rule.priority == top_priority]
        decision_rule = max(candidates, key=lambda rule: EFFECT_RANK[rule.effect])
        decision = decision_rule.effect
        reason = f"matched rule {decision_rule.rule_id}"
    else:
        decision_rule = None
        decision = defaults.get(action, defaults.get("*", "ask"))
        reason = "default policy"

    return {
        "decision": decision,
        "reason": reason,
        "action": action,
        "command": command,
        "cwd": cwd,
        "actor": actor,
        "target_paths": target_paths,
        "matched_rules": [
            {
                "id": rule.rule_id,
                "effect": rule.effect,
                "priority": rule.priority,
                "description": rule.description,
            }
            for rule in matched_rules
        ],
        "defaults": defaults,
        "winning_rule": None
        if decision_rule is None
        else {
            "id": decision_rule.rule_id,
            "effect": decision_rule.effect,
            "priority": decision_rule.priority,
            "description": decision_rule.description,
        },
    }

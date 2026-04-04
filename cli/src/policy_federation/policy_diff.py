"""Policy diffing and comparison utilities."""
from __future__ import annotations

import json
from typing import Any


def diff_policies(before: dict, after: dict) -> dict:
    """
    Compare two resolved policies and identify differences.

    Args:
        before: The first (original) policy dictionary
        after: The second (modified) policy dictionary

    Returns:
        A dictionary with the following structure:
        {
            "added_rules": [...],           # Rules only in after
            "removed_rules": [...],         # Rules only in before
            "modified_rules": [...],        # Rules in both but with differences
            "effect_changes": [...]         # Rules where effect changed
        }
    """
    before_rules = _extract_rules(before)
    after_rules = _extract_rules(after)

    # Only include rules with valid IDs
    before_ids = {rule["id"]: rule for rule in before_rules if "id" in rule}
    after_ids = {rule["id"]: rule for rule in after_rules if "id" in rule}

    added = []
    removed = []
    modified = []
    effect_changes = []

    # Find added and modified rules
    for rule_id, after_rule in after_ids.items():
        if rule_id not in before_ids:
            added.append(after_rule)
        else:
            before_rule = before_ids[rule_id]
            # Check for modifications
            if before_rule != after_rule:
                diff_entry = {"id": rule_id, "before": before_rule, "after": after_rule}
                modified.append(diff_entry)

                # Check for effect changes specifically
                if before_rule.get("effect") != after_rule.get("effect"):
                    effect_changes.append({
                        "id": rule_id,
                        "before_effect": before_rule.get("effect"),
                        "after_effect": after_rule.get("effect"),
                        "description": after_rule.get("description", ""),
                    })

    # Find removed rules
    for rule_id, before_rule in before_ids.items():
        if rule_id not in after_ids:
            removed.append(before_rule)

    return {
        "added_rules": added,
        "removed_rules": removed,
        "modified_rules": modified,
        "effect_changes": effect_changes,
    }


def _extract_rules(policy: dict) -> list[dict]:
    """Extract all authorization rules from a policy dictionary."""
    authorization = policy.get("authorization") or {}
    rules = authorization.get("rules") or []
    return rules if isinstance(rules, list) else []

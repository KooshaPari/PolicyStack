"""Policy file editing utilities for rule management."""
from __future__ import annotations

from pathlib import Path
import yaml

from .validate import validate_policy_file
from .authorization import validate_authorization_block


def add_rule(policy_path: Path, rule: dict) -> None:
    """Append a rule to the authorization.rules list in a YAML policy file.

    Args:
        policy_path: Path to the policy YAML file
        rule: Rule dictionary with id, effect, actions, priority, and optional match conditions

    Raises:
        ValueError: If the policy is invalid after adding the rule
    """
    with policy_path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict):
        raise ValueError("Policy file must be a YAML mapping")

    # Initialize authorization section if missing
    if "policy" not in doc:
        doc["policy"] = {}
    if "authorization" not in doc["policy"]:
        doc["policy"]["authorization"] = {}

    # Initialize rules list if missing
    if "rules" not in doc["policy"]["authorization"]:
        doc["policy"]["authorization"]["rules"] = []

    rules = doc["policy"]["authorization"]["rules"]
    if not isinstance(rules, list):
        raise ValueError("policy.authorization.rules must be a list")

    # Check for duplicate rule ID
    rule_id = rule.get("id")
    if not rule_id:
        raise ValueError("Rule must have an 'id' field")

    existing_ids = {r.get("id") for r in rules if isinstance(r, dict)}
    if rule_id in existing_ids:
        raise ValueError(f"Rule with id '{rule_id}' already exists")

    # Append the new rule
    rules.append(rule)

    # Validate the entire document
    validate_authorization_block({"policy": doc["policy"]})

    # Write back with safe dumper to preserve YAML structure
    with policy_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)


def remove_rule(policy_path: Path, rule_id: str) -> None:
    """Remove a rule by ID from the authorization.rules list.

    Args:
        policy_path: Path to the policy YAML file
        rule_id: ID of the rule to remove

    Raises:
        ValueError: If the rule doesn't exist or the policy becomes invalid after removal
    """
    with policy_path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict):
        raise ValueError("Policy file must be a YAML mapping")

    # Access authorization.rules
    authorization = doc.get("policy", {}).get("authorization", {})
    rules = authorization.get("rules", [])

    if not isinstance(rules, list):
        raise ValueError("policy.authorization.rules must be a list")

    # Find and remove the rule
    original_count = len(rules)
    rules[:] = [r for r in rules if isinstance(r, dict) and r.get("id") != rule_id]

    if len(rules) == original_count:
        raise ValueError(f"Rule with id '{rule_id}' not found")

    # Validate the entire document
    validate_authorization_block({"policy": doc["policy"]})

    # Write back with safe dumper
    with policy_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)

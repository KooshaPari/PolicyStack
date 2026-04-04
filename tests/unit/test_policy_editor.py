"""Tests for policy editing functionality."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from support import CLI_SRC
from policy_federation.policy_editor import add_rule, remove_rule


@pytest.fixture
def temp_policy_file():
    """Create a temporary policy file for testing."""
    content = {
        "version": "1.0",
        "id": "test/policy",
        "scope": "system",
        "policy": {
            "authorization": {
                "defaults": {
                    "exec": "ask",
                },
                "rules": [
                    {
                        "id": "existing-rule",
                        "effect": "allow",
                        "actions": ["read"],
                        "priority": 10,
                        "match": {
                            "command_patterns": ["ls *"],
                        },
                    }
                ],
            }
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(content, f)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


def test_add_rule_simple(temp_policy_file):
    """Test adding a simple rule without match conditions."""
    rule = {
        "id": "new-rule",
        "effect": "deny",
        "actions": ["write"],
        "priority": 20,
    }
    add_rule(temp_policy_file, rule)

    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)

    rules = doc["policy"]["authorization"]["rules"]
    assert len(rules) == 2
    assert rules[1]["id"] == "new-rule"
    assert rules[1]["effect"] == "deny"
    assert rules[1]["priority"] == 20


def test_add_rule_with_match_conditions(temp_policy_file):
    """Test adding a rule with match conditions."""
    rule = {
        "id": "networked-exec",
        "effect": "ask",
        "actions": ["exec"],
        "priority": 50,
        "match": {
            "command_patterns": ["curl *", "wget *"],
            "cwd_patterns": ["/tmp/*"],
        },
    }
    add_rule(temp_policy_file, rule)

    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)

    rules = doc["policy"]["authorization"]["rules"]
    added_rule = rules[1]
    assert added_rule["id"] == "networked-exec"
    assert added_rule["match"]["command_patterns"] == ["curl *", "wget *"]
    assert added_rule["match"]["cwd_patterns"] == ["/tmp/*"]


def test_add_rule_duplicate_id(temp_policy_file):
    """Test that adding a rule with duplicate ID fails."""
    rule = {
        "id": "existing-rule",  # This ID already exists
        "effect": "allow",
        "actions": ["read"],
        "priority": 5,
    }
    with pytest.raises(ValueError, match="already exists"):
        add_rule(temp_policy_file, rule)


def test_add_rule_missing_id(temp_policy_file):
    """Test that adding a rule without an ID fails."""
    rule = {
        "effect": "allow",
        "actions": ["read"],
        "priority": 5,
    }
    with pytest.raises(ValueError, match="must have an 'id'"):
        add_rule(temp_policy_file, rule)


def test_add_rule_invalid_effect(temp_policy_file):
    """Test that invalid effect value is caught by validation."""
    rule = {
        "id": "bad-rule",
        "effect": "invalid",
        "actions": ["read"],
        "priority": 5,
    }
    with pytest.raises(ValueError, match="must be allow|deny|ask"):
        add_rule(temp_policy_file, rule)


def test_remove_rule_existing(temp_policy_file):
    """Test removing an existing rule."""
    remove_rule(temp_policy_file, "existing-rule")

    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)

    rules = doc["policy"]["authorization"]["rules"]
    assert len(rules) == 0
    rule_ids = [r["id"] for r in rules]
    assert "existing-rule" not in rule_ids


def test_remove_rule_nonexistent(temp_policy_file):
    """Test that removing a non-existent rule fails."""
    with pytest.raises(ValueError, match="not found"):
        remove_rule(temp_policy_file, "nonexistent-rule")


def test_add_then_remove(temp_policy_file):
    """Test adding and then removing a rule."""
    rule = {
        "id": "temp-rule",
        "effect": "allow",
        "actions": ["read"],
        "priority": 15,
    }
    add_rule(temp_policy_file, rule)

    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)
    assert len(doc["policy"]["authorization"]["rules"]) == 2

    remove_rule(temp_policy_file, "temp-rule")

    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)
    assert len(doc["policy"]["authorization"]["rules"]) == 1
    assert doc["policy"]["authorization"]["rules"][0]["id"] == "existing-rule"


def test_add_rule_initializes_authorization(tmp_path):
    """Test that add_rule initializes authorization section if missing."""
    # Create a policy file without authorization
    policy_file = tmp_path / "policy.yaml"
    content = {
        "version": "1.0",
        "id": "test/policy",
        "scope": "system",
        "policy": {},
    }
    with policy_file.open("w") as f:
        yaml.safe_dump(content, f)

    rule = {
        "id": "new-rule",
        "effect": "allow",
        "actions": ["read"],
        "priority": 0,
    }
    add_rule(policy_file, rule)

    with policy_file.open() as f:
        doc = yaml.safe_load(f)

    assert "authorization" in doc["policy"]
    assert "rules" in doc["policy"]["authorization"]
    assert len(doc["policy"]["authorization"]["rules"]) == 1
    assert doc["policy"]["authorization"]["rules"][0]["id"] == "new-rule"

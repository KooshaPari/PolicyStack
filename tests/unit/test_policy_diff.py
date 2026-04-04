"""Tests for policy diff functionality."""
from __future__ import annotations

import pytest

from support import REPO_ROOT  # noqa: F401
from policy_federation.policy_diff import diff_policies


class TestDiffPolicies:
    """Test policy diffing."""

    def test_empty_policies(self) -> None:
        """Test diffing empty policies."""
        result = diff_policies({}, {})
        assert result["added_rules"] == []
        assert result["removed_rules"] == []
        assert result["modified_rules"] == []
        assert result["effect_changes"] == []

    def test_no_authorization_rules(self) -> None:
        """Test policies without authorization rules."""
        before = {"some_key": "some_value"}
        after = {"some_key": "some_value"}
        result = diff_policies(before, after)
        assert result["added_rules"] == []
        assert result["removed_rules"] == []
        assert result["modified_rules"] == []
        assert result["effect_changes"] == []

    def test_added_rules(self) -> None:
        """Test detection of added rules."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]},
                    {"id": "rule2", "effect": "deny", "actions": ["write"]}
                ]
            }
        }
        result = diff_policies(before, after)
        assert len(result["added_rules"]) == 1
        assert result["added_rules"][0]["id"] == "rule2"
        assert result["added_rules"][0]["effect"] == "deny"
        assert result["removed_rules"] == []
        assert result["modified_rules"] == []

    def test_removed_rules(self) -> None:
        """Test detection of removed rules."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]},
                    {"id": "rule2", "effect": "deny", "actions": ["write"]}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]}
                ]
            }
        }
        result = diff_policies(before, after)
        assert result["added_rules"] == []
        assert len(result["removed_rules"]) == 1
        assert result["removed_rules"][0]["id"] == "rule2"
        assert result["modified_rules"] == []

    def test_modified_rules(self) -> None:
        """Test detection of modified rules."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"], "priority": 1}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read", "write"], "priority": 1}
                ]
            }
        }
        result = diff_policies(before, after)
        assert result["added_rules"] == []
        assert result["removed_rules"] == []
        assert len(result["modified_rules"]) == 1
        assert result["modified_rules"][0]["id"] == "rule1"
        assert result["modified_rules"][0]["before"]["actions"] == ["read"]
        assert result["modified_rules"][0]["after"]["actions"] == ["read", "write"]

    def test_effect_change(self) -> None:
        """Test detection of effect changes."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"], "description": "Allow read"}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "deny", "actions": ["read"], "description": "Allow read"}
                ]
            }
        }
        result = diff_policies(before, after)
        assert len(result["effect_changes"]) == 1
        change = result["effect_changes"][0]
        assert change["id"] == "rule1"
        assert change["before_effect"] == "allow"
        assert change["after_effect"] == "deny"
        assert change["description"] == "Allow read"

    def test_multiple_effect_changes(self) -> None:
        """Test detection of multiple effect changes."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]},
                    {"id": "rule2", "effect": "deny", "actions": ["write"]},
                    {"id": "rule3", "effect": "ask", "actions": ["execute"]}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "deny", "actions": ["read"]},
                    {"id": "rule2", "effect": "allow", "actions": ["write"]},
                    {"id": "rule3", "effect": "ask", "actions": ["execute"]}
                ]
            }
        }
        result = diff_policies(before, after)
        assert len(result["effect_changes"]) == 2
        ids = {change["id"] for change in result["effect_changes"]}
        assert ids == {"rule1", "rule2"}

    def test_complex_diff(self) -> None:
        """Test a complex diff with multiple types of changes."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]},
                    {"id": "rule2", "effect": "deny", "actions": ["write"]},
                    {"id": "rule3", "effect": "ask", "actions": ["execute"]},
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "deny", "actions": ["read"]},  # changed effect
                    {"id": "rule2", "effect": "deny", "actions": ["write", "delete"]},  # modified
                    # rule3 removed
                    {"id": "rule4", "effect": "allow", "actions": ["create"]},  # added
                ]
            }
        }
        result = diff_policies(before, after)

        # Check added
        assert len(result["added_rules"]) == 1
        assert result["added_rules"][0]["id"] == "rule4"

        # Check removed
        assert len(result["removed_rules"]) == 1
        assert result["removed_rules"][0]["id"] == "rule3"

        # Check modified (rule1 and rule2 changed, rule1 has effect change)
        assert len(result["modified_rules"]) == 2
        modified_ids = {rule["id"] for rule in result["modified_rules"]}
        assert modified_ids == {"rule1", "rule2"}

        # Check effect changes (rule1 changed)
        assert len(result["effect_changes"]) == 1
        assert result["effect_changes"][0]["id"] == "rule1"
        assert result["effect_changes"][0]["before_effect"] == "allow"
        assert result["effect_changes"][0]["after_effect"] == "deny"

    def test_modified_and_effect_change(self) -> None:
        """Test rule that is both modified and has effect change."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"], "priority": 1}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "deny", "actions": ["read"], "priority": 2}
                ]
            }
        }
        result = diff_policies(before, after)

        # Should be in both modified and effect_changes
        assert len(result["modified_rules"]) == 1
        assert result["modified_rules"][0]["id"] == "rule1"
        assert len(result["effect_changes"]) == 1
        assert result["effect_changes"][0]["id"] == "rule1"

    def test_rules_without_ids(self) -> None:
        """Test handling of malformed rules without IDs."""
        before = {
            "authorization": {
                "rules": [
                    {"effect": "allow", "actions": ["read"]}  # no id
                ]
            }
        }
        after = {
            "authorization": {
                "rules": []
            }
        }
        # Should handle gracefully without crashing
        result = diff_policies(before, after)
        # Malformed rule won't be tracked since it has no id
        # So it should appear as removed
        assert len(result["removed_rules"]) == 0  # Invalid rule not tracked
        assert len(result["added_rules"]) == 0
        assert len(result["modified_rules"]) == 0
        assert len(result["effect_changes"]) == 0

    def test_null_authorization(self) -> None:
        """Test policies with null authorization section."""
        before = {"authorization": None}
        after = {"authorization": None}
        result = diff_policies(before, after)
        assert result["added_rules"] == []
        assert result["removed_rules"] == []
        assert result["modified_rules"] == []

    def test_missing_authorization_section(self) -> None:
        """Test policies without authorization section."""
        before = {"other_section": {"data": "value"}}
        after = {"other_section": {"data": "value"}}
        result = diff_policies(before, after)
        assert result["added_rules"] == []
        assert result["removed_rules"] == []
        assert result["modified_rules"] == []

    def test_effect_change_without_other_changes(self) -> None:
        """Test that effect-only changes are detected."""
        before = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "allow", "actions": ["read"]}
                ]
            }
        }
        after = {
            "authorization": {
                "rules": [
                    {"id": "rule1", "effect": "deny", "actions": ["read"]}
                ]
            }
        }
        result = diff_policies(before, after)

        # Should be modified
        assert len(result["modified_rules"]) == 1
        # Should have effect change
        assert len(result["effect_changes"]) == 1

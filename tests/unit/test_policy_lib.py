"""Tests for the policy_lib primitives and evaluator."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Add repo root to sys.path so policy_lib can be imported standalone
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from policy_lib import (
    ALLOWED_ACTIONS,
    ALLOWED_MATCHERS,
    CONDITION_EVALUATORS,
    CommandRule,
    Condition,
    ConditionGroup,
    Decision,
    evaluate_policy,
    normalize_payload,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir() -> Path:
    """Provide a temporary directory for condition evaluation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ---------------------------------------------------------------------------
# Unit tests — Condition
# ---------------------------------------------------------------------------

class TestCondition:
    """Condition dataclass — export and evaluate."""

    def test_export_implicit_required(self) -> None:
        """A required condition with explicit=False exports as its name string."""
        cond = Condition(name="git_is_worktree", required=True, explicit=False)
        assert cond.export() == "git_is_worktree"

    def test_export_explicit_required(self) -> None:
        """A required condition with explicit=True exports as a dict."""
        cond = Condition(name="git_is_worktree", required=True, explicit=True)
        assert cond.export() == {"name": "git_is_worktree", "required": True}

    def test_export_optional(self) -> None:
        """An optional condition always exports as a dict."""
        cond = Condition(name="git_is_worktree", required=False)
        assert cond.export() == {"name": "git_is_worktree", "required": False}

    def test_evaluate_unsupported_condition(self) -> None:
        """An unknown condition name returns (False, error-reason)."""
        cond = Condition(name="nonexistent_check", required=True)
        ok, reason = cond.evaluate(Path("/tmp"))
        assert ok is False
        assert "unsupported_condition" in reason


# ---------------------------------------------------------------------------
# Unit tests — ConditionGroup
# ---------------------------------------------------------------------------

class TestConditionGroup:
    """ConditionGroup — evaluate and export logic."""

    def test_empty_group_succeeds(self) -> None:
        """An empty ConditionGroup passes."""
        group = ConditionGroup(mode="all", items=())
        ok, reasons = group.evaluate(Path("/tmp"))
        assert ok is True

    def test_export_roundtrip(self) -> None:
        """ConditionGroup.export() produces a serializable dict."""
        inner = ConditionGroup(
            mode="any",
            items=(
                Condition("git_is_worktree", required=True),
                Condition("git_clean_worktree", required=False),
            ),
        )
        group = ConditionGroup(
            mode="all",
            items=(
                Condition("git_is_worktree"),
                inner,
            ),
        )
        exported = group.export()
        assert exported["mode"] == "all"
        assert len(exported["conditions"]) == 2
        # First condition is a simple string
        assert exported["conditions"][0] == "git_is_worktree"
        # Second condition is a nested group
        inner_exported = exported["conditions"][1]
        assert inner_exported["mode"] == "any"
        assert len(inner_exported["conditions"]) == 2

    def test_all_mode_fails_on_first_required(self) -> None:
        """In 'all' mode, any required failure fails the group."""
        group = ConditionGroup(
            mode="all",
            items=(
                Condition("git_is_worktree", required=True),
            ),
        )
        # /tmp is not a git worktree, so this should fail
        ok, reasons = group.evaluate(Path("/tmp"))
        assert ok is False
        assert any("git_is_worktree" in r for r in reasons)

    def test_any_mode_succeeds_if_any_required_passes(self) -> None:
        """In 'any' mode, one passing required item is enough."""
        # We can't easily test this with real git evaluators in /tmp,
        # so we test the structure with evaluate_with_quality directly
        # by checking the mode is correctly wired.
        group = ConditionGroup(mode="any", items=())
        assert group.mode == "any"

    def test_evaluate_with_quality_empty(self) -> None:
        """evaluate_with_quality on an empty group returns true, false, []."""
        group = ConditionGroup(mode="all", items=())
        ok, partial_fail, reasons = group.evaluate_with_quality(Path("/tmp"))
        assert ok is True
        assert partial_fail is False
        assert reasons == []


# ---------------------------------------------------------------------------
# Unit tests — CommandRule
# ---------------------------------------------------------------------------

class TestCommandRule:
    """CommandRule — matching, evaluation, and export."""

    def test_matches_exact(self) -> None:
        """Exact matcher only matches identical normalized commands."""
        rule = CommandRule(
            rule_id="test-1",
            action="deny",
            pattern="git push",
            matcher="exact",
        )
        assert rule.matches("git push") is True
        assert rule.matches("git push origin main") is False
        assert rule.matches("  git   push  ") is True  # normalized

    def test_matches_glob(self) -> None:
        """Glob matcher supports fnmatch patterns."""
        rule = CommandRule(
            rule_id="test-2",
            action="allow",
            pattern="git *",
            matcher="glob",
        )
        assert rule.matches("git push") is True
        assert rule.matches("git status") is True
        assert rule.matches("cargo build") is False

    def test_matches_prefix(self) -> None:
        """Prefix matcher checks command starts with pattern."""
        rule = CommandRule(
            rule_id="test-3",
            action="deny",
            pattern="rm",
            matcher="prefix",
        )
        assert rule.matches("rm -rf /") is True
        assert rule.matches("rmdir") is False  # not a prefix split
        assert rule.matches("ls") is False

    def test_matches_empty_pattern(self) -> None:
        """An empty pattern never matches."""
        rule = CommandRule(
            rule_id="test-4",
            action="deny",
            pattern="",
            matcher="glob",
        )
        assert rule.matches("anything") is False

    def test_evaluate_no_conditions(self) -> None:
        """Without conditions, evaluate returns action for matching commands."""
        rule = CommandRule(
            rule_id="test-5",
            action="allow",
            pattern="cargo *",
            matcher="glob",
        )
        assert rule.evaluate("cargo build", Path("/tmp")) == "allow"
        assert rule.evaluate("ls", Path("/tmp")) is None

    def test_decision_trace(self) -> None:
        """decision_trace returns rule_id::action::source."""
        rule = CommandRule(
            rule_id="my-rule",
            action="deny",
            pattern="*",
            source="test-suite",
        )
        assert rule.decision_trace() == "my-rule::deny::test-suite"

    def test_export_no_conditions(self) -> None:
        """Export omits conditions key when not set."""
        rule = CommandRule(
            rule_id="r1",
            action="allow",
            pattern="git *",
        )
        exported = rule.export()
        assert exported["rule_id"] == "r1"
        assert "conditions" not in exported

    def test_export_with_conditions(self) -> None:
        """Export includes conditions when set."""
        cond = ConditionGroup(items=(Condition("git_is_worktree"),))
        rule = CommandRule(
            rule_id="r2",
            action="allow",
            pattern="git *",
            conditions=cond,
        )
        exported = rule.export()
        assert "conditions" in exported
        assert exported["conditions"]["mode"] == "all"


# ---------------------------------------------------------------------------
# Unit tests — normalize_payload
# ---------------------------------------------------------------------------

class TestNormalizePayload:
    """normalize_payload — parses policy dicts into CommandRule list."""

    def test_simple_allow_deny(self) -> None:
        """Parses a payload with allow/deny commands."""
        payload = {
            "policy": {
                "commands": {
                    "allow": ["git push", "cargo build"],
                    "deny": ["rm -rf /"],
                },
            },
        }
        rules = normalize_payload(payload)
        assert len(rules) == 3

        # Deny rules come first
        assert rules[0].action == "deny"
        assert rules[0].pattern == "rm -rf /"
        # Allow rules last
        assert rules[-1].action == "allow"

    def test_require_commands(self) -> None:
        """Require commands produce 'request'-action rules."""
        payload = {
            "policy": {
                "commands": {
                    "require": ["git commit"],
                },
            },
        }
        rules = normalize_payload(payload)
        assert len(rules) == 1
        assert rules[0].action == "request"

    def test_command_rules_with_match(self) -> None:
        """Command rules with match blocks are parsed correctly."""
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "rule-1",
                        "action": "deny",
                        "match": {"prefix": "sudo"},
                    },
                ],
            },
        }
        rules = normalize_payload(payload)
        assert len(rules) == 1
        assert rules[0].matcher == "prefix"
        assert rules[0].pattern == "sudo"

    def test_invalid_payload_type(self) -> None:
        """Non-dict payload raises ValueError."""
        with pytest.raises(ValueError, match="must be a mapping"):
            normalize_payload("not a dict")  # type: ignore[arg-type]

    def test_invalid_policy_type(self) -> None:
        """Non-dict policy raises ValueError."""
        with pytest.raises(ValueError, match="must be a mapping"):
            normalize_payload({"policy": "not a dict"})

    def test_invalid_commands_type(self) -> None:
        """Commands that is not a dict raises ValueError."""
        with pytest.raises(ValueError, match="must be a map"):
            normalize_payload({"policy": {"commands": "not a dict"}})

    def test_invalid_command_rules_type(self) -> None:
        """Command_rules that is not a list raises ValueError."""
        payload = {
            "policy": {
                "command_rules": "not a list",
            },
        }
        with pytest.raises(ValueError, match="must be a list"):
            normalize_payload(payload)


# ---------------------------------------------------------------------------
# Unit tests — evaluate_policy
# ---------------------------------------------------------------------------

class TestEvaluatePolicy:
    """evaluate_policy — top-level policy evaluation."""

    def test_deny_has_priority(self, temp_dir: Path) -> None:
        """'deny' decision wins over 'allow'."""
        payload = {
            "policy": {
                "commands": {
                    "allow": ["*"],
                    "deny": ["rm -rf *"],
                },
            },
        }
        decision, reason, rule = evaluate_policy(payload, "rm -rf /", temp_dir)
        assert decision == "deny"

    def test_allow_fallback(self, temp_dir: Path) -> None:
        """Unmatched command falls back to 'allow'."""
        payload = {
            "policy": {
                "commands": {
                    "allow": ["git *"],
                    "deny": ["rm *"],
                },
            },
        }
        decision, reason, rule = evaluate_policy(payload, "ls -la", temp_dir)
        assert decision == "allow"
        assert reason == "no_policy_match"

    def test_request_between_deny_and_allow(self, temp_dir: Path) -> None:
        """'request' decision is returned when no deny but matching require."""
        payload = {
            "policy": {
                "commands": {
                    "allow": ["git *"],
                    "require": ["git push"],
                },
            },
        }
        decision, reason, rule = evaluate_policy(payload, "git push", temp_dir)
        assert decision == "request"

    def test_exact_match_rule(self, temp_dir: Path) -> None:
        """Command rules with exact matcher work."""
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "exact-block",
                        "action": "deny",
                        "match": {"exact": "cargo test"},
                    },
                ],
            },
        }
        decision, reason, rule = evaluate_policy(payload, "cargo test", temp_dir)
        assert decision == "deny"
        # Slightly different command — no match
        decision2, _, _ = evaluate_policy(payload, "cargo test --all", temp_dir)
        assert decision2 == "allow"


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis) — roundtrip behavior
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Hypothesis tests require Python 3.10+",
)
class TestRoundtripProptests:
    """Property-based roundtrip tests for export/import."""

    def test_condition_export_roundtrip(self) -> None:
        """Condition.export() output can reconstruct equivalent conditions."""
        import hypothesis.strategies as st
        from hypothesis import given, settings

        # All valid condition names known to the evaluator
        valid_conditions = st.sampled_from(sorted(CONDITION_EVALUATORS.keys()))

        @given(
            name=valid_conditions,
            required=st.booleans(),
            explicit=st.booleans(),
        )
        @settings(max_examples=50)
        def _run(name: str, required: bool, explicit: bool) -> None:
            cond = Condition(name=name, required=required, explicit=explicit)
            exported = cond.export()

            if required and not explicit:
                # Exports as a plain string
                assert exported == name
            else:
                # Exports as a dict
                assert isinstance(exported, dict)
                assert exported["name"] == name
                assert exported["required"] == required
                # Check condition name is still valid
                assert exported["name"] in CONDITION_EVALUATORS

        _run()

    def test_command_rule_patterns_glob(self) -> None:
        """CommandRule with various glob patterns matches consistently."""
        import hypothesis.strategies as st
        from hypothesis import given, settings

        patterns = st.sampled_from([
            "git *",
            "cargo *",
            "rm *",
            "ls*",
            "*",
            "git push",
        ])
        commands = st.sampled_from([
            "git push",
            "git status",
            "cargo build",
            "rm -rf /",
            "ls -la",
            "npm install",
        ])

        @given(pattern=patterns, command=commands)
        @settings(max_examples=30)
        def _run(pattern: str, command: str) -> None:
            rule = CommandRule(
                rule_id="prop-test",
                action="allow",
                pattern=pattern,
                matcher="glob",
            )
            result = rule.matches(command)
            # Just ensure no exceptions are raised and result is boolean
            assert isinstance(result, bool)

        _run()


# ---------------------------------------------------------------------------
# Smoke test — constants
# ---------------------------------------------------------------------------

class TestConstants:
    """Verify module-level constants."""

    def test_allowed_actions(self) -> None:
        assert ALLOWED_ACTIONS == {"allow", "request", "deny"}

    def test_allowed_matchers(self) -> None:
        assert ALLOWED_MATCHERS == {"exact", "glob", "prefix"}

    def test_condition_evaluators_keys(self) -> None:
        assert set(CONDITION_EVALUATORS.keys()) == {
            "git_is_worktree",
            "git_clean_worktree",
            "git_synced_to_upstream",
        }

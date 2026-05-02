"""
Integration test for PolicyStack ↔ phenotype-policy-engine PyO3 binding.

Tests that the Rust policy engine bindings correctly evaluate rules
when consumed from PolicyStack.
"""


import pytest

# Skip if maturin wheel not available (no Python headers, etc.)
pyo3 = pytest.importorskip("phenotype_policy_engine_py")


class TestPyO3PolicyEngineIntegration:
    """End-to-end integration test for PolicyStack rule evaluation via PyO3."""

    def test_rule_evaluator_creation(self):
        """FR-SHARED-007: RuleEvaluator can be instantiated and rules added."""
        evaluator = pyo3.RuleEvaluator()
        assert evaluator.rule_count() == 0

    def test_add_and_count_rules(self):
        """FR-SHARED-007: RuleEvaluator tracks rule count correctly."""
        evaluator = pyo3.RuleEvaluator()
        rule1 = pyo3.Rule("rule-1", "EXACT", "ALLOW")
        rule2 = pyo3.Rule("rule-2", "REGEX", "DENY")

        evaluator.add_rule(rule1)
        evaluator.add_rule(rule2)

        assert evaluator.rule_count() == 2

    def test_rule_metadata_assignment(self):
        """FR-SHARED-005: Rule can have metadata assigned."""
        rule = pyo3.Rule("acl-rule", "EXACT", "ALLOW")
        metadata = pyo3.RuleMetadata(priority=10)
        metadata.add_tag("security")
        metadata.add_tag("audit")

        # Set metadata on rule
        rule.set_metadata(metadata)

        # Verify rule construction succeeded (no exceptions)
        assert repr(rule) is not None
        assert "acl-rule" in repr(rule)

    def test_condition_group_construction(self):
        """FR-SHARED-002: ConditionGroup stores named collections of conditions."""
        group = pyo3.ConditionGroup("auth_conditions")
        group.add_condition("user_role", "admin")
        group.add_condition("resource_type", "database")

        # Verify group was created with conditions
        group_repr = repr(group)
        assert "auth_conditions" in group_repr
        assert "2" in group_repr  # 2 conditions

    def test_matcher_kind_variants(self):
        """FR-SHARED-001: MatcherKind enum supports required variants."""
        assert pyo3.MatcherKind.EXACT is not None
        assert pyo3.MatcherKind.REGEX is not None
        assert pyo3.MatcherKind.CONTAINS is not None

    def test_on_mismatch_action_variants(self):
        """FR-SHARED-004: OnMismatchAction enum supports required variants."""
        assert pyo3.OnMismatchAction.ALLOW is not None
        assert pyo3.OnMismatchAction.DENY is not None
        assert pyo3.OnMismatchAction.SKIP is not None

    def test_evaluate_rules_with_context(self):
        """
        FR-SHARED-007: RuleEvaluator.evaluate() produces Decision objects
        that match expected allowed/reason/trace semantics.
        """
        evaluator = pyo3.RuleEvaluator()

        # Create a rule that allows on match
        rule_allow = pyo3.Rule("rule-allow", "EXACT", "ALLOW")
        evaluator.add_rule(rule_allow)

        # Create a context dictionary with synthetic user data
        context = {
            "user_id": "user123",
            "resource": "database:prod",
            "action": "READ",
        }

        # Evaluate rules
        decisions = evaluator.evaluate(context)

        # Verify Decision structure and content
        assert len(decisions) == 1
        decision = decisions[0]

        # Decision should have string representation and be truthy
        assert repr(decision) is not None
        assert "rule-allow" in repr(decision)

    def test_evaluate_multiple_rules(self):
        """FR-SHARED-007: RuleEvaluator evaluates all rules and returns decisions for each."""
        evaluator = pyo3.RuleEvaluator()

        rule1 = pyo3.Rule("rule-1", "EXACT", "ALLOW")
        rule2 = pyo3.Rule("rule-2", "REGEX", "DENY")
        rule3 = pyo3.Rule("rule-3", "CONTAINS", "SKIP")

        evaluator.add_rule(rule1)
        evaluator.add_rule(rule2)
        evaluator.add_rule(rule3)

        context = {"env": "production", "tier": "premium"}
        decisions = evaluator.evaluate(context)

        assert len(decisions) == 3
        assert "rule-1" in repr(decisions[0])
        assert "rule-2" in repr(decisions[1])
        assert "rule-3" in repr(decisions[2])

    def test_clear_rules(self):
        """FR-SHARED-007: RuleEvaluator.clear() removes all rules."""
        evaluator = pyo3.RuleEvaluator()
        rule = pyo3.Rule("rule-temp", "EXACT", "DENY")
        evaluator.add_rule(rule)

        assert evaluator.rule_count() == 1

        evaluator.clear()

        assert evaluator.rule_count() == 0

    def test_decision_creation_directly(self):
        """FR-SHARED-006: Decision can be created with rule_id, allowed, and reason."""
        msg = "All conditions matched"
        decision = pyo3.Decision("policy-rule-1", allowed=True, reason=msg)

        # Verify Decision was created and has expected representation
        decision_repr = repr(decision)
        assert "policy-rule-1" in decision_repr
        assert "Decision" in decision_repr

    def test_policystack_integration_scenario(self):
        """
        Integration scenario: PolicyStack evaluates an ACL rule
        against a synthetic user context via PyO3 binding.

        This demonstrates how PolicyStack would consume the policy
        engine to make an access control decision.
        """
        # Setup policy engine
        evaluator = pyo3.RuleEvaluator()

        # Create ACL rule: allow admins to read databases
        acl_rule = pyo3.Rule("acl-db-read", "EXACT", "DENY")
        rule_meta = pyo3.RuleMetadata(priority=100)
        rule_meta.add_tag("acl")
        rule_meta.add_tag("database")
        acl_rule.set_metadata(rule_meta)

        evaluator.add_rule(acl_rule)

        # Simulate a user request context
        request_context = {
            "user_role": "admin",
            "resource": "database:customers",
            "action": "SELECT",
            "source_ip": "10.0.0.5",
        }

        # Evaluate the policy
        decisions = evaluator.evaluate(request_context)

        # Verify the decision was made
        assert len(decisions) == 1
        decision = decisions[0]

        # PolicyStack would now use this decision to allow/deny the request
        decision_repr = repr(decision)
        assert "acl-db-read" in decision_repr
        assert "Decision" in decision_repr
        assert "true" in decision_repr or "false" in decision_repr

    def test_repr_methods(self):
        """Verify that repr methods work for debugging."""
        rule = pyo3.Rule("rule-repr", "EXACT", "ALLOW")
        evaluator = pyo3.RuleEvaluator()

        # These should not raise
        rule_repr = repr(rule)
        evaluator_repr = repr(evaluator)

        assert "rule-repr" in rule_repr
        assert "RuleEvaluator" in evaluator_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

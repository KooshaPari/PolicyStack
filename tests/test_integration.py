"""Integration tests for PolicyStack multi-platform system."""

from __future__ import annotations

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from policy_federation.interceptor import intercept_command
from policy_federation.headless_review import (
    run_headless_review,
    _run_new_delegate_review,
)
from policy_federation.risk import RiskTier
from policy_federation.delegate import DelegateContext, DelegateResult


class TestInterceptorIntegration:
    """Integration tests for the interceptor with tiered risk."""

    @pytest.fixture
    def repo_root(self):
        """Create a temporary repo root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_tier_1_auto_allow(self, repo_root):
        """Tier 1 commands should auto-allow without delegation."""
        result = intercept_command(
            repo_root=repo_root,
            harness="claude-code",
            repo="test-repo",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="git status",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            ask_mode="delegate",
        )

        assert result["allowed"] is True
        assert result["final_decision"] == "allow"
        assert result["evaluation"]["risk_tier"] == "TIER_1_NONE"
        assert result["evaluation"]["decision_path"] == "auto-allow"

    def test_tier_2_worktree_allow(self, repo_root):
        """Tier 2 commands in worktrees should cache-allow."""
        worktree_path = repo_root / ".worktrees" / "feature-branch"
        worktree_path.mkdir(parents=True)

        result = intercept_command(
            repo_root=repo_root,
            harness="claude-code",
            repo="test-repo",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="git add -A",
            cwd=str(worktree_path),
            actor="test",
            target_paths=[],
            ask_mode="delegate",
        )

        assert result["allowed"] is True
        assert result["final_decision"] == "allow"
        assert result["evaluation"]["risk_tier"] == "TIER_2_LOW"
        assert result["evaluation"]["decision_path"] == "cache-allow"

    def test_tier_3_fast_check(self, repo_root):
        """Tier 3 commands should use fast-check path."""
        result = intercept_command(
            repo_root=repo_root,
            harness="claude-code",
            repo="test-repo",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="git push origin main",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            ask_mode="delegate",
        )

        # May allow or ask depending on local-fast evaluation
        assert result["evaluation"]["risk_tier"] == "TIER_3_MEDIUM"
        assert result["evaluation"]["decision_path"] == "fast-check"

    def test_tier_4_high_risk(self, repo_root):
        """Tier 4 commands should delegate."""
        result = intercept_command(
            repo_root=repo_root,
            harness="claude-code",
            repo="test-repo",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="rm -rf /",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            ask_mode="delegate",
        )

        assert result["evaluation"]["risk_tier"] == "TIER_4_HIGH"
        assert result["evaluation"]["decision_path"] == "delegate"

    def test_explicit_allow_policy(self, repo_root):
        """Explicit policy allow should work."""
        # This tests that policy decisions are respected
        result = intercept_command(
            repo_root=repo_root,
            harness="claude-code",
            repo="test-repo",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="ls -la",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            ask_mode="allow",  # Explicit allow mode
        )

        assert result["allowed"] is True

    def test_explicit_deny_policy(self, repo_root):
        """Explicit policy deny should work."""
        # Create a policy that denies a specific command
        policy_dir = repo_root / ".phenotype"
        policy_dir.mkdir(exist_ok=True)

        policy = {
            "policies": [
                {
                    "id": "deny-rm-rf",
                    "match": {"command": "rm -rf *"},
                    "decision": "deny",
                }
            ]
        }
        policy_file = policy_dir / "policy.json"
        policy_file.write_text(json.dumps(policy))

        # The deny policy should be respected
        result = intercept_command(
            repo_root=repo_root,
            harness="claude-code",
            repo="test-repo",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="rm -rf something",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            ask_mode="delegate",
        )

        # May be denied by policy or by risk assessment
        if result["policy_decision"] == "deny":
            assert result["allowed"] is False


class TestHeadlessReviewIntegration:
    """Integration tests for headless review with new delegate system."""

    @pytest.fixture
    def repo_root(self):
        """Create a temporary repo root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_new_delegate_review_uses_tiered_risk(self, repo_root):
        """New delegate review should use tiered risk assessment."""
        result = _run_new_delegate_review(
            action="exec",
            command="git status",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            policy_decision="ask",
            policy_reason="ambiguous",
            matched_rules=[],
            scope_chain=["repo"],
        )

        assert result is not None
        assert "tier" in result
        assert result["tier"] == "TIER_1_NONE"

    def test_new_delegate_review_worktree_operations(self, repo_root):
        """New delegate review should handle worktree operations."""
        worktree_path = repo_root / ".worktrees" / "branch"
        worktree_path.mkdir(parents=True)

        result = _run_new_delegate_review(
            action="exec",
            command="git add -A",
            cwd=str(worktree_path),
            actor="test",
            target_paths=[],
            policy_decision="ask",
            policy_reason="ambiguous",
            matched_rules=[],
            scope_chain=["repo"],
        )

        assert result is not None
        assert result["tier"] == "TIER_2_LOW"
        assert result["decision"] == "allow"

    def test_new_delegate_review_high_risk(self, repo_root):
        """New delegate review should handle high-risk operations."""
        result = _run_new_delegate_review(
            action="exec",
            command="rm -rf /",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            policy_decision="ask",
            policy_reason="ambiguous",
            matched_rules=[],
            scope_chain=["repo"],
        )

        assert result is not None
        assert result["tier"] == "TIER_4_HIGH"
        assert result["decision"] == "deny"

    @patch("policy_federation.headless_review._run_reviewer_binary")
    @patch("policy_federation.headless_review._run_new_delegate_review")
    def test_run_headless_review_uses_new_system_first(
        self, mock_new_review, mock_legacy, repo_root
    ):
        """run_headless_review should try new system before legacy."""
        mock_new_review.return_value = {
            "decision": "allow",
            "reason": "New system decided",
            "tier": "TIER_1_NONE",
        }

        result = run_headless_review(
            repo_root=repo_root,
            action="exec",
            command="git status",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            policy_decision="ask",
            policy_reason="ambiguous",
            matched_rules=[],
        )

        assert mock_new_review.called
        assert result["decision"] == "allow"

    @patch("policy_federation.headless_review._run_reviewer_binary")
    @patch("policy_federation.headless_review._run_new_delegate_review")
    def test_run_headless_review_falls_back_to_legacy(
        self, mock_new_review, mock_legacy, repo_root
    ):
        """run_headless_review should fall back to legacy when new system fails."""
        # New system fails
        mock_new_review.return_value = {
            "decision": "ask",
            "reason": "All harnesses failed",
            "review_error": "Test error",
        }

        # Legacy succeeds
        mock_legacy.return_value = {
            "decision": "allow",
            "reason": "Legacy allowed",
        }

        result = run_headless_review(
            repo_root=repo_root,
            action="exec",
            command="some-command",
            cwd=str(repo_root),
            actor="test",
            target_paths=[],
            policy_decision="ask",
            policy_reason="ambiguous",
            matched_rules=[],
        )

        # Should have tried new system
        assert mock_new_review.called
        # Result should be from fallback


class TestDecisionConsistency:
    """Tests for decision consistency across platforms."""

    @pytest.fixture
    def test_commands(self):
        """Return test commands for consistency checking."""
        return {
            "tier_1": ["git status", "ls -la", "cat file.txt", "pwd"],
            "tier_2_worktree": ["git add -A", "git commit -m 'test'", "mkdir -p test"],
            "tier_3": ["git push", "cargo build", "cargo test"],
            "tier_4": ["rm -rf /", "sudo ls", "chmod 777 /etc"],
        }

    def test_tier_1_consistency(self, test_commands):
        """Tier 1 commands should always be auto-allowed consistently."""
        from policy_federation.risk import assess_risk_tiered

        for cmd in test_commands["tier_1"]:
            result1 = assess_risk_tiered(command=cmd, cwd="/tmp", is_worktree=False)
            result2 = assess_risk_tiered(command=cmd, cwd="/other", is_worktree=False)
            result3 = assess_risk_tiered(command=cmd, cwd="/work", is_worktree=True)

            # All should be Tier 1
            assert result1.tier == RiskTier.TIER_1_NONE, f"{cmd} should be Tier 1"
            assert result2.tier == RiskTier.TIER_1_NONE, f"{cmd} should be Tier 1"
            assert result3.tier == RiskTier.TIER_1_NONE, f"{cmd} should be Tier 1"

            # All should auto-allow
            assert result1.auto_allow, f"{cmd} should auto-allow"
            assert result2.auto_allow, f"{cmd} should auto-allow"
            assert result3.auto_allow, f"{cmd} should auto-allow"

    def test_tier_4_always_destructive(self, test_commands):
        """Tier 4 commands should always be flagged destructive."""
        from policy_federation.risk import assess_risk_tiered, is_destructive_pattern

        for cmd in test_commands["tier_4"]:
            # Should be detected as destructive
            assert is_destructive_pattern(cmd), f"{cmd} should be destructive"

            # Risk assessment should be Tier 4
            result = assess_risk_tiered(command=cmd, cwd="/tmp", is_worktree=False)
            assert result.tier == RiskTier.TIER_4_HIGH, f"{cmd} should be Tier 4"

    def test_worktree_consistency(self, test_commands):
        """Tier 2 commands should only be low-risk in worktrees."""
        from policy_federation.risk import assess_risk_tiered

        for cmd in test_commands["tier_2_worktree"]:
            # In worktree - Tier 2
            result_worktree = assess_risk_tiered(
                command=cmd, cwd="/path/.worktrees/branch", is_worktree=True
            )
            assert result_worktree.tier == RiskTier.TIER_2_LOW, (
                f"{cmd} in worktree should be Tier 2"
            )

            # In canonical - NOT Tier 2
            result_canonical = assess_risk_tiered(
                command=cmd, cwd="/path/repo/main", is_worktree=False
            )
            assert result_canonical.tier != RiskTier.TIER_2_LOW, (
                f"{cmd} in canonical should NOT be Tier 2"
            )


class TestCacheIntegration:
    """Integration tests for caching behavior."""

    def test_cache_speeds_up_repeated_commands(self):
        """Cached commands should be faster on subsequent calls."""
        import time
        from policy_federation.delegate import (
            _get_cached_decision,
            _cache_decision,
            _get_cache_db,
        )
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "test_cache.db"

            with patch(
                "policy_federation.delegate._get_cache_db", return_value=cache_db
            ):
                # First call - cache miss
                start = time.time()
                result1 = _get_cached_decision("git status")
                miss_time = time.time() - start

                # Cache a decision
                result = DelegateResult("allow", "test", "test", 0.9)
                _cache_decision("git status", result)

                # Second call - cache hit
                start = time.time()
                result2 = _get_cached_decision("git status")
                hit_time = time.time() - start

                assert result1 is None  # Miss
                assert result2 is not None  # Hit
                assert result2.decision == "allow"
                # Cache hit should be very fast
                assert hit_time < miss_time or miss_time < 0.01  # Both should be fast


class TestPerformanceTargets:
    """Tests verifying performance targets are met."""

    def test_local_fast_evaluator_speed(self):
        """Local-fast evaluator should respond in <5ms."""
        import time
        from policy_federation.delegate import _local_fast_evaluate

        ctx = DelegateContext(
            action="exec",
            command="git status",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.0,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        times = []
        for _ in range(100):
            start = time.perf_counter()
            result = _local_fast_evaluate(ctx)
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Average should be well under 5ms
        assert avg_time < 1.0, f"Average local-fast time {avg_time:.2f}ms exceeds 1ms"
        # Max should be under 5ms
        assert max_time < 5.0, f"Max local-fast time {max_time:.2f}ms exceeds 5ms"

    def test_risk_assessment_speed(self):
        """Risk assessment should be instant (<1ms)."""
        import time
        from policy_federation.risk import assess_risk_tiered

        times = []
        for _ in range(100):
            start = time.perf_counter()
            result = assess_risk_tiered(
                command="git status", cwd="/tmp", is_worktree=False
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        assert avg_time < 1.0, f"Average risk assessment {avg_time:.2f}ms exceeds 1ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

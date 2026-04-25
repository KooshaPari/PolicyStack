"""Tests for multi-platform delegation system."""

from __future__ import annotations

import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

from policy_federation.delegate import (
    DelegateContext,
    DelegateResult,
    delegate_ask,
    _local_fast_evaluate,
    _get_cached_decision,
    _cache_decision,
    _hash_command,
    _extract_pattern,
    render_delegate_prompt,
    HARNESS_FALLBACK,
    HARNESS_CONFIG,
    get_cache_stats,
    clear_cache,
    _auto_detect_harness,
    _cli_available,
)


class TestLocalFastEvaluator:
    """Test local-fast evaluator for instant decisions."""

    def test_tier_1_read_operations(self):
        """Local-fast should allow Tier 1 read operations."""
        ctx = DelegateContext(
            action="exec",
            command="git status",
            cwd="/home/user/.worktrees/branch",
            target_paths=[],
            risk_score=0.0,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        result = _local_fast_evaluate(ctx)
        assert result is not None
        assert result.decision == "allow"
        assert "read-safe" in result.source

    def test_tier_2_worktree_operations(self):
        """Local-fast should allow Tier 2 worktree operations."""
        ctx = DelegateContext(
            action="exec",
            command="git add -A",
            cwd="/home/user/.worktrees/branch",
            target_paths=[],
            risk_score=0.1,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        result = _local_fast_evaluate(ctx)
        assert result is not None
        assert result.decision == "allow"
        assert "worktree-safe" in result.source

    def test_tier_2_not_in_worktree(self):
        """Tier 2 patterns should not auto-allow outside worktrees."""
        ctx = DelegateContext(
            action="exec",
            command="git add -A",
            cwd="/home/user/repos/main",  # Not a worktree
            target_paths=[],
            risk_score=0.1,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        result = _local_fast_evaluate(ctx)
        assert result is None  # Can't decide locally

    def test_tier_4_destructive_patterns(self):
        """Local-fast should deny Tier 4 destructive patterns."""
        ctx = DelegateContext(
            action="exec",
            command="rm -rf /",
            cwd="/home/user/.worktrees/branch",
            target_paths=[],
            risk_score=1.0,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        result = _local_fast_evaluate(ctx)
        assert result is not None
        assert result.decision == "deny"
        assert "risk-pattern" in result.source

    def test_unknown_command_returns_none(self):
        """Unknown commands should return None for delegation."""
        ctx = DelegateContext(
            action="exec",
            command="some-unknown-command --weird-flag",
            cwd="/home/user/.worktrees/branch",
            target_paths=[],
            risk_score=0.5,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        result = _local_fast_evaluate(ctx)
        assert result is None  # Can't decide locally


class TestDecisionCaching:
    """Test decision caching functionality."""

    def test_cache_basic_operations(self):
        """Test basic cache write and read."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "test_cache.db"

            # Patch the cache path
            with patch(
                "policy_federation.delegate._get_cache_db", return_value=cache_db
            ):
                # Clear and init cache
                clear_cache()

                # Cache a decision
                result = DelegateResult(
                    decision="allow",
                    reasoning="Test decision",
                    source="test",
                    confidence=0.95,
                )
                _cache_decision("git status", result)

                # Read it back
                cached = _get_cached_decision("git status")
                assert cached is not None
                assert cached.decision == "allow"
                assert cached.source == "cache:test"

    def test_cache_ttl_expiration(self):
        """Test that expired entries are not returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "test_cache.db"

            with patch(
                "policy_federation.delegate._get_cache_db", return_value=cache_db
            ):
                import time

                # Cache with very old timestamp
                with patch("policy_federation.delegate.time.time", return_value=0):
                    result = DelegateResult("allow", "old", "test", 0.9)
                    _cache_decision("old command", result)

                # Try to read with current time (should be expired)
                with patch("policy_federation.delegate.time.time", return_value=100000):
                    cached = _get_cached_decision("old command")
                    assert cached is None  # Expired

    def test_pattern_matching(self):
        """Test pattern-based cache matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "test_cache.db"

            with patch(
                "policy_federation.delegate._get_cache_db", return_value=cache_db
            ):
                # Cache for specific path
                result = DelegateResult("allow", "test", "test", 0.9)
                _cache_decision("cat /path/to/file.txt", result)

                # Should match similar command with different path
                cached = _get_cached_decision("cat /other/path/file.md")
                assert cached is not None
                assert "pattern" in cached.source

    def test_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "test_cache.db"

            with patch(
                "policy_federation.delegate._get_cache_db", return_value=cache_db
            ):
                clear_cache()

                # Add some entries
                for i in range(5):
                    result = DelegateResult("allow", f"test {i}", "test", 0.9)
                    _cache_decision(f"command {i}", result)

                stats = get_cache_stats()
                assert stats["total_entries"] == 5
                assert "by_decision" in stats


class TestCommandHashing:
    """Test command hashing and pattern extraction."""

    def test_hash_consistency(self):
        """Same command should produce same hash."""
        hash1 = _hash_command("git status")
        hash2 = _hash_command("git status")
        assert hash1 == hash2

    def test_hash_uniqueness(self):
        """Different commands should produce different hashes."""
        hash1 = _hash_command("git status")
        hash2 = _hash_command("git log")
        assert hash1 != hash2

    def test_pattern_extraction(self):
        """Pattern extraction should normalize commands."""
        # Paths replaced
        pattern = _extract_pattern("cat /path/to/file.txt")
        assert "<PATH>" in pattern
        assert "/path/to/file.txt" not in pattern

        # Numbers replaced
        pattern = _extract_pattern("head -20 file")
        assert "<NUM>" in pattern
        assert "-20" not in pattern


class TestPromptRendering:
    """Test delegate prompt rendering."""

    def test_prompt_includes_all_context(self):
        """Prompt should include all context information."""
        ctx = DelegateContext(
            action="exec",
            command="git push origin main",
            cwd="/home/user/repo",
            target_paths=["/home/user/repo/.git"],
            risk_score=0.5,
            risk_factors={"factors": ["test"]},
            rule_id="git-push-rule",
            rule_description="Git push rule",
            scope_chain=["repo", "branch"],
        )

        prompt = render_delegate_prompt(ctx)
        assert "git push origin main" in prompt
        assert "exec" in prompt
        assert "/home/user/repo" in prompt
        assert "0.5" in prompt
        assert "git-push-rule" in prompt
        assert "repo" in prompt


class TestHarnessConfiguration:
    """Test harness configuration."""

    def test_harness_fallback_chains(self):
        """All harnesses should have fallback chains."""
        for harness in HARNESS_CONFIG.keys():
            assert harness in HARNESS_FALLBACK, f"{harness} should have fallback chain"

    def test_harness_config_complete(self):
        """All harness configs should have required fields."""
        for harness, config in HARNESS_CONFIG.items():
            if "api_url" not in config:
                assert "cli" in config, f"{harness} should have cli or api_url"
            assert "timeout" in config, f"{harness} should have timeout"


class TestHarnessAutoDetection:
    """Test harness auto-detection."""

    @patch("policy_federation.delegate._cli_available")
    def test_auto_detect_prefers_available(self, mock_available):
        """Auto-detect should prefer first available CLI."""

        # Only opencode available
        def side_effect(cli):
            return cli == "opencode"

        mock_available.side_effect = side_effect

        result = _auto_detect_harness()
        assert result == "opencode"

    @patch("policy_federation.delegate._cli_available")
    def test_auto_detect_returns_none_if_none_available(self, mock_available):
        """Auto-detect should return None if no CLIs available."""
        mock_available.return_value = False

        result = _auto_detect_harness()
        assert result is None


class TestCLIAvailability:
    """Test CLI availability checking."""

    @patch("policy_federation.delegate.subprocess.run")
    def test_cli_available_true(self, mock_run):
        """Should return True if CLI responds to --version."""
        mock_run.return_value = MagicMock(returncode=0)
        assert _cli_available("somecli") is True

    @patch("policy_federation.delegate.subprocess.run")
    def test_cli_available_false_on_error(self, mock_run):
        """Should return False if CLI not found."""
        mock_run.side_effect = FileNotFoundError()
        assert _cli_available("somecli") is False

    @patch("policy_federation.delegate.subprocess.run")
    def test_cli_available_false_on_timeout(self, mock_run):
        """Should return False if CLI times out."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)
        assert _cli_available("somecli") is False


class TestDelegateAskIntegration:
    """Integration tests for delegate_ask function."""

    @patch("policy_federation.delegate._local_fast_evaluate")
    def test_delegate_ask_uses_local_fast(self, mock_local_fast):
        """delegate_ask should use local-fast when available."""
        mock_local_fast.return_value = DelegateResult(
            decision="allow",
            reasoning="Fast allow",
            source="local-fast:test",
            confidence=0.95,
        )

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

        result = delegate_ask(ctx, use_local_fast=True, use_cache=False)
        assert result.decision == "allow"
        assert "local-fast" in result.source

    def test_delegate_ask_falls_back_to_ask(self):
        """delegate_ask should return ask when all methods fail."""
        ctx = DelegateContext(
            action="exec",
            command="unknown-weird-command-that-fails",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.5,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        # No harness configured, should return ask
        with patch(
            "policy_federation.delegate._auto_detect_harness", return_value=None
        ):
            result = delegate_ask(ctx, use_local_fast=True, use_cache=False)
            assert result.decision == "ask"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

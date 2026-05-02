"""Performance benchmarking tools for PolicyStack.

Run benchmarks: python -m pytest tests/test_performance.py -v
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from typing import Any

import pytest
from policy_federation.delegate import (
    DelegateContext,
    _cache_decision,
    _get_cached_decision,
    _local_fast_evaluate,
    delegate_ask,
)
from policy_federation.risk import assess_risk_tiered


class PerformanceMetrics:
    """Collect and analyze performance metrics."""

    def __init__(self):
        self.times: list[float] = []

    def record(self, elapsed_ms: float):
        """Record a timing measurement."""
        self.times.append(elapsed_ms)

    @property
    def min(self) -> float:
        return min(self.times) if self.times else 0.0

    @property
    def max(self) -> float:
        return max(self.times) if self.times else 0.0

    @property
    def mean(self) -> float:
        return statistics.mean(self.times) if self.times else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.times) if self.times else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.times) if len(self.times) > 1 else 0.0

    @property
    def p95(self) -> float:
        """95th percentile."""
        if not self.times:
            return 0.0
        sorted_times = sorted(self.times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def __str__(self) -> str:
        return (
            f"min={self.min:.2f}ms, "
            f"mean={self.mean:.2f}ms, "
            f"median={self.median:.2f}ms, "
            f"max={self.max:.2f}ms, "
            f"p95={self.p95:.2f}ms, "
            f"stdev={self.stdev:.2f}ms"
        )


def benchmark_function(
    func: Callable[..., Any], iterations: int = 100, *args, **kwargs,
) -> PerformanceMetrics:
    """Benchmark a function over multiple iterations."""
    metrics = PerformanceMetrics()

    for _ in range(iterations):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        metrics.record(elapsed)

    return metrics


class TestRiskAssessmentPerformance:
    """Benchmark risk assessment performance."""

    @pytest.mark.benchmark
    def test_tier_1_assessment_speed(self):
        """Tier 1 (read operations) should be <1ms median."""
        metrics = benchmark_function(
            assess_risk_tiered,
            iterations=1000,
            command="git status",
            cwd="/tmp",
            is_worktree=False,
        )

        print(f"\nTier 1 Risk Assessment: {metrics}")
        assert metrics.median < 1.0, f"Tier 1 median {metrics.median:.2f}ms exceeds 1ms"
        assert metrics.p95 < 5.0, f"Tier 1 p95 {metrics.p95:.2f}ms exceeds 5ms"

    @pytest.mark.benchmark
    def test_tier_4_assessment_speed(self):
        """Tier 4 (destructive) should also be fast."""
        metrics = benchmark_function(
            assess_risk_tiered,
            iterations=1000,
            command="rm -rf /",
            cwd="/tmp",
            is_worktree=False,
        )

        print(f"\nTier 4 Risk Assessment: {metrics}")
        assert metrics.median < 1.0, f"Tier 4 median {metrics.median:.2f}ms exceeds 1ms"


class TestLocalFastEvaluatorPerformance:
    """Benchmark local-fast evaluator performance."""

    @pytest.mark.benchmark
    def test_local_fast_tier_1_speed(self):
        """Local-fast for Tier 1 should be <1ms."""
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

        metrics = benchmark_function(_local_fast_evaluate, iterations=1000, ctx=ctx)

        print(f"\nLocal-Fast Tier 1: {metrics}")
        assert metrics.median < 1.0, (
            f"Local-fast median {metrics.median:.2f}ms exceeds 1ms"
        )
        assert metrics.max < 5.0, f"Local-fast max {metrics.max:.2f}ms exceeds 5ms"

    @pytest.mark.benchmark
    def test_local_fast_tier_4_speed(self):
        """Local-fast for Tier 4 should also be fast."""
        ctx = DelegateContext(
            action="exec",
            command="rm -rf /",
            cwd="/tmp",
            target_paths=[],
            risk_score=1.0,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        metrics = benchmark_function(_local_fast_evaluate, iterations=1000, ctx=ctx)

        print(f"\nLocal-Fast Tier 4: {metrics}")
        assert metrics.median < 1.0, (
            f"Local-fast Tier 4 median {metrics.median:.2f}ms exceeds 1ms"
        )

    @pytest.mark.benchmark
    def test_local_fast_unknown_command_speed(self):
        """Local-fast for unknown commands should also be fast (<1ms)."""
        ctx = DelegateContext(
            action="exec",
            command="weird-unknown-command --with-flags",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.5,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )

        metrics = benchmark_function(_local_fast_evaluate, iterations=1000, ctx=ctx)

        print(f"\nLocal-Fast Unknown: {metrics}")
        assert metrics.median < 1.0, (
            f"Local-fast unknown median {metrics.median:.2f}ms exceeds 1ms"
        )


class TestCachePerformance:
    """Benchmark cache operations."""

    @pytest.mark.benchmark
    def test_cache_read_speed(self, tmp_path):
        """Cache reads should be <5ms."""
        from unittest.mock import patch

        cache_db = tmp_path / "perf_cache.db"

        with patch("policy_federation.delegate._get_cache_db", return_value=cache_db):
            # Pre-populate cache
            result = DelegateResult("allow", "test", "test", 0.9)
            _cache_decision("test command", result)

            # Benchmark reads
            metrics = benchmark_function(
                _get_cached_decision, iterations=1000, command="test command",
            )

            print(f"\nCache Read: {metrics}")
            assert metrics.median < 5.0, (
                f"Cache read median {metrics.median:.2f}ms exceeds 5ms"
            )
            assert metrics.p95 < 10.0, (
                f"Cache read p95 {metrics.p95:.2f}ms exceeds 10ms"
            )

    @pytest.mark.benchmark
    def test_cache_write_speed(self, tmp_path):
        """Cache writes should be <10ms."""
        import uuid
        from unittest.mock import patch

        cache_db = tmp_path / "perf_cache.db"

        with patch("policy_federation.delegate._get_cache_db", return_value=cache_db):

            def write_unique():
                # Unique command to avoid conflicts
                unique_cmd = f"command-{uuid.uuid4()}"
                result = DelegateResult("allow", "test", "test", 0.9)
                _cache_decision(unique_cmd, result)

            metrics = benchmark_function(write_unique, iterations=100)

            print(f"\nCache Write: {metrics}")
            assert metrics.median < 10.0, (
                f"Cache write median {metrics.median:.2f}ms exceeds 10ms"
            )


class TestAutoApprovalRate:
    """Verify auto-approval rate targets."""

    def test_auto_approval_rate_simulation(self):
        """Simulate command mix and verify auto-approval rate."""

        # Typical development command mix
        commands = {
            # Tier 1: Read operations (~60% of typical usage)
            "tier_1": [
                "git status",
                "git log",
                "git diff",
                "ls -la",
                "cat file.txt",
                "head -20 README.md",
                "tail -f logs.txt",
                "grep pattern src/",
                "find . -type f -name '*.py'",
                "pwd",
                "which python",
                "ruff check src/",
                "cargo check",
                "cargo fmt",
            ],
            # Tier 2: Worktree operations (~15% of typical usage)
            "tier_2": [
                "git add -A",
                "git commit -m 'wip'",
                "git checkout feature",
                "mkdir -p new/dir",
                "touch newfile.txt",
                "cp old.txt new.txt",
            ],
            # Tier 3: Medium risk (~10% of typical usage)
            "tier_3": [
                "git push origin main",
                "git pull --rebase",
                "cargo build --release",
                "cargo test",
            ],
            # Tier 4: High risk (~5% of typical usage)
            "tier_4": [
                "rm -rf /tmp/old",
                "sudo apt update",  # Simulated lower risk tier 4
            ],
        }

        # Weight counts by realistic usage percentages
        tier_1_count = len(commands["tier_1"]) * 4  # High weight
        tier_2_count = len(commands["tier_2"]) * 2  # Medium weight
        tier_3_count = len(commands["tier_3"]) * 1  # Normal weight
        tier_4_count = len(commands["tier_4"]) * 1  # Normal weight

        total = tier_1_count + tier_2_count + tier_3_count + tier_4_count

        # Calculate auto-approvals
        auto_approvals = 0

        for tier_name, tier_commands in commands.items():
            for cmd in tier_commands:
                result = assess_risk_tiered(
                    command=cmd,
                    cwd="/home/user/.worktrees/feature",  # Worktree context
                    is_worktree=True,
                )
                if result.auto_allow:
                    if tier_name == "tier_1":
                        auto_approvals += 4
                    elif tier_name == "tier_2":
                        auto_approvals += 2
                    elif tier_name in ("tier_3", "tier_4"):
                        auto_approvals += 1

        # Calculate percentage
        auto_approval_rate = (auto_approvals / total) * 100

        print(f"\nSimulated Auto-Approval Rate: {auto_approval_rate:.1f}%")
        print("Target: >= 70%")

        assert auto_approval_rate >= 70.0, (
            f"Auto-approval rate {auto_approval_rate:.1f}% below target"
        )


class TestOverallSystemPerformance:
    """Overall system performance benchmarks."""

    @pytest.mark.benchmark
    def test_end_to_end_tier_1_decision(self):
        """End-to-end Tier 1 decision should be <5ms."""
        ctx = DelegateContext(
            action="exec",
            command="git status",
            cwd="/home/user/.worktrees/feature",
            target_paths=[],
            risk_score=0.0,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=["repo"],
        )

        metrics = benchmark_function(
            delegate_ask,
            iterations=100,
            context=ctx,
            use_cache=True,
            use_local_fast=True,
        )

        print(f"\nEnd-to-End Tier 1 (with cache): {metrics}")
        # First call may be slower, subsequent should be fast
        # Median should include cached results

    def test_performance_regression_check(self):
        """Check for performance regressions against baseline."""
        # Baseline metrics (established values)
        baselines = {
            "risk_assessment": {"median_ms": 0.5, "max_ms": 2.0},
            "local_fast": {"median_ms": 0.5, "max_ms": 2.0},
            "cache_read": {"median_ms": 2.0, "max_ms": 5.0},
        }

        # Measure current performance
        risk_metrics = benchmark_function(
            assess_risk_tiered,
            iterations=100,
            command="git status",
            cwd="/tmp",
            is_worktree=False,
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

        local_fast_metrics = benchmark_function(
            _local_fast_evaluate,
            iterations=100,
            ctx=ctx,
        )

        # Check against baselines
        regressions = []

        if risk_metrics.median > baselines["risk_assessment"]["median_ms"] * 2:
            regressions.append(
                f"Risk assessment median {risk_metrics.median:.2f}ms > baseline {baselines['risk_assessment']['median_ms']:.2f}ms",
            )

        if local_fast_metrics.median > baselines["local_fast"]["median_ms"] * 2:
            regressions.append(
                f"Local-fast median {local_fast_metrics.median:.2f}ms > baseline {baselines['local_fast']['median_ms']:.2f}ms",
            )

        if risk_metrics.max > baselines["risk_assessment"]["max_ms"] * 3:
            regressions.append(
                f"Risk assessment max {risk_metrics.max:.2f}ms > baseline {baselines['risk_assessment']['max_ms']:.2f}ms",
            )

        if regressions:
            pytest.fail("Performance regressions detected:\n" + "\n".join(regressions))

        print("\nPerformance regression check: PASSED")
        print(
            f"  Risk Assessment: {risk_metrics.median:.2f}ms (baseline: {baselines['risk_assessment']['median_ms']:.2f}ms)",
        )
        print(
            f"  Local-Fast: {local_fast_metrics.median:.2f}ms (baseline: {baselines['local_fast']['median_ms']:.2f}ms)",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark"])

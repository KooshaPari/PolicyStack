"""Risk scoring engine for policy ask decisions.

Provides both weighted risk scoring and 4-tier risk assessment:
- Tier 1: No risk → Auto-allow
- Tier 2: Low risk → Cache-allow
- Tier 3: Medium risk → Fast-check
- Tier 4: High risk → Delegate
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .runtime_artifacts import read_audit_log

# ============================================================================
# 4-Tier Risk Assessment System
# ============================================================================


class RiskTier(Enum):
    """Risk tiers for policy decisions."""

    TIER_1_NONE = 1  # Auto-allow (read ops, safe queries)
    TIER_2_LOW = 2  # Cache-allow (previous patterns, worktree ops)
    TIER_3_MEDIUM = 3  # Fast-check (validation needed)
    TIER_4_HIGH = 4  # Delegate (destructive ops)


@dataclass
class RiskAssessment:
    """Result of risk assessment."""

    tier: RiskTier
    score: float  # 0.0 to 1.0
    factors: list[str]
    auto_allow: bool
    cache_key: str | None


# Safe read patterns (Tier 1) - Auto-allow
TIER_1_PATTERNS = [
    (r"^git\s+status", "git status"),
    (r"^git\s+log", "git log"),
    (r"^git\s+diff", "git diff"),
    (r"^git\s+show", "git show"),
    (r"^git\s+branch\s+-a", "git branch list"),
    (r"^ls\s", "list directory"),
    (r"^ll\s", "list directory (ll)"),
    (r"^cat\s", "concatenate file"),
    (r"^head\s", "read file head"),
    (r"^tail\s", "read file tail"),
    (r"^grep\s", "search text"),
    (r"^find\s.*-type\s+f", "find files"),
    (r"^echo\s", "echo text"),
    (r"^pwd$", "print working directory"),
    (r"^which\s", "find command"),
    (r"^ruff\s+check", "ruff check (read)"),
    (r"^cargo\s+check", "cargo check (read)"),
    (r"^cargo\s+fmt", "cargo fmt (read)"),
    (r"^cargo\s+clippy", "cargo clippy (read)"),
]

# Low risk patterns for worktrees (Tier 2) - Cache-allow
TIER_2_PATTERNS = [
    (r"^git\s+add\s", "git add"),
    (r"^git\s+commit\s", "git commit"),
    (r"^git\s+checkout\s", "git checkout"),
    (r"^git\s+switch\s", "git switch"),
    (r"^mkdir\s+-p\s", "mkdir -p"),
    (r"^touch\s", "touch file"),
    (r"^cp\s", "copy file"),
    (r"^ln\s+-s\s", "symlink"),
    (r"^ruff\s+format", "ruff format"),
]

# Medium risk patterns (Tier 3) - Fast-check
TIER_3_PATTERNS = [
    (r"^git\s+push", "git push"),
    (r"^git\s+pull", "git pull"),
    (r"^git\s+merge", "git merge"),
    (r"^git\s+rebase", "git rebase"),
    (r"^mv\s", "move file"),
    (r"^cargo\s+build", "cargo build"),
    (r"^cargo\s+test", "cargo test"),
]

# High risk patterns (Tier 4) - Always delegate
TIER_4_PATTERNS = [
    (r"rm\s+-rf\s+/", "rm -rf root"),
    (r"rm\s+-rf\s+~", "rm -rf home"),
    (r"sudo\s", "sudo command"),
    (r"chmod\s+777", "chmod 777"),
    (r"curl\s.*\|\s*sh", "curl pipe to shell"),
    (r"wget\s.*\|\s*sh", "wget pipe to shell"),
    (r"eval\s*\$", "eval variable"),
]

# Paths that trigger higher risk
HIGH_RISK_PATHS = [
    r"/etc/",
    r"/usr/(bin|sbin|lib)/",
    r"/bin/",
    r"/sbin/",
]


def assess_risk_tiered(
    command: str,
    cwd: str | None = None,
    target_paths: list[str] | None = None,
    is_worktree: bool = False,
    is_canonical: bool = False,
) -> RiskAssessment:
    """Assess risk tier for a command using 4-tier system.

    Args:
        command: The command to assess
        cwd: Current working directory
        target_paths: Paths the command operates on
        is_worktree: Whether in a worktree (lower risk)
        is_canonical: Whether in canonical repo (higher risk)

    Returns:
        RiskAssessment with tier, score, and factors
    """
    factors = []
    score = 0.0

    # Check for Tier 4 (high risk) patterns first
    for pattern, description in TIER_4_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            factors.append(f"High-risk pattern: {description}")
            return RiskAssessment(
                tier=RiskTier.TIER_4_HIGH,
                score=1.0,
                factors=factors,
                auto_allow=False,
                cache_key=None,
            )

    # Check for Tier 1 (safe) patterns
    for pattern, description in TIER_1_PATTERNS:
        if re.match(pattern, command, re.IGNORECASE):
            factors.append(f"Safe pattern: {description}")
            return RiskAssessment(
                tier=RiskTier.TIER_1_NONE,
                score=0.0,
                factors=factors,
                auto_allow=True,
                cache_key=_pattern_key(command),
            )

    # Check for Tier 2 (low risk) patterns in worktrees
    if is_worktree:
        for pattern, description in TIER_2_PATTERNS:
            if re.match(pattern, command, re.IGNORECASE):
                factors.append(f"Low-risk worktree pattern: {description}")
                return RiskAssessment(
                    tier=RiskTier.TIER_2_LOW,
                    score=0.1,
                    factors=factors,
                    auto_allow=True,
                    cache_key=_pattern_key(command),
                )

    # Check for Tier 3 (medium risk) patterns
    for pattern, description in TIER_3_PATTERNS:
        if re.match(pattern, command, re.IGNORECASE):
            factors.append(f"Medium-risk pattern: {description}")
            return RiskAssessment(
                tier=RiskTier.TIER_3_MEDIUM,
                score=0.5,
                factors=factors,
                auto_allow=False,
                cache_key=_pattern_key(command),
            )

    # Check target paths for high-risk locations
    if target_paths:
        for path in target_paths:
            for high_risk in HIGH_RISK_PATHS:
                if re.search(high_risk, path):
                    factors.append(f"High-risk path: {path}")
                    score = max(score, 0.8)

    # Check if in canonical repo (higher risk)
    if is_canonical:
        factors.append("Operating in canonical repository")
        score = min(1.0, score + 0.2)

    # Determine final tier
    if score >= 0.7:
        tier = RiskTier.TIER_4_HIGH
        auto_allow = False
    elif score >= 0.3:
        tier = RiskTier.TIER_3_MEDIUM
        auto_allow = False
    elif is_worktree:
        tier = RiskTier.TIER_2_LOW
        auto_allow = True
    else:
        tier = RiskTier.TIER_3_MEDIUM
        auto_allow = False

    if not factors:
        factors.append("Unrecognized command pattern")

    return RiskAssessment(
        tier=tier,
        score=score,
        factors=factors,
        auto_allow=auto_allow,
        cache_key=_pattern_key(command) if auto_allow else None,
    )


def _pattern_key(command: str) -> str:
    """Generate a cache key for a command pattern."""
    key = re.sub(r"\s+/[^\s]+", " <PATH>", command)
    key = re.sub(r"\s+-\w+\s+\S+", " <ARG>", key)
    key = re.sub(r"\s+\d+", " <NUM>", key)
    return key.strip()


def get_tiered_decision_path(assessment: RiskAssessment) -> str:
    """Get the decision path for a risk tier."""
    paths = {
        RiskTier.TIER_1_NONE: "auto-allow",
        RiskTier.TIER_2_LOW: "cache-allow",
        RiskTier.TIER_3_MEDIUM: "fast-check",
        RiskTier.TIER_4_HIGH: "delegate",
    }
    return paths.get(assessment.tier, "delegate")


# ============================================================================
# Legacy Risk Scoring (keep for backward compatibility)
# ============================================================================

# Worktree path patterns that indicate low-risk scope
WORKTREE_PATTERNS = [
    "*-wtrees/*",
    "*/.worktrees/*",
    "*/PROJECT-wtrees/*",
    "*/worktrees/*",
]


def score_risk(
    *,
    action: str,
    command: str,
    cwd: str | None,
    target_paths: list[str] | None,
    bypass_indicators: list[str] | None = None,
    audit_log_path: Path | None = None,
) -> dict:
    """Score the risk of an ask decision. Returns dict with score (0.0-1.0), factors, and delegation_eligible."""
    factors = {}

    # Factor 1: Action type (weight 0.3)
    action_scores = {"exec": 0.2, "write": 0.6, "network": 0.8}
    factors["action_type"] = {"value": action_scores.get(action, 0.5), "weight": 0.3}

    # Factor 2: Target scope (weight 0.3) - worktree=low, canonical=high, system=highest
    scope_score = _score_target_scope(cwd, target_paths)
    factors["target_scope"] = {"value": scope_score, "weight": 0.3}

    # Factor 3: Command familiarity from audit (weight 0.2)
    familiarity_score = _score_familiarity(command, audit_log_path)
    factors["command_familiarity"] = {"value": familiarity_score, "weight": 0.2}

    # Factor 4: Bypass indicators (weight 0.2)
    bypass_score = 0.8 if bypass_indicators else 0.0
    factors["bypass_indicators"] = {"value": bypass_score, "weight": 0.2}

    # Weighted sum
    total = sum(f["value"] * f["weight"] for f in factors.values())

    return {
        "score": round(total, 3),
        "factors": factors,
        "delegation_eligible": total < 0.7,  # Only delegate if risk < 0.7
        "auto_delegate": total < 0.3,  # Auto-delegate without flagging if very low risk
    }


def _score_target_scope(cwd: str | None, target_paths: list[str] | None) -> float:
    """Score based on whether targets are in worktrees (safe) or canonical (risky)."""
    paths_to_check = list(target_paths or [])
    if cwd:
        paths_to_check.append(cwd)
    if not paths_to_check:
        return 0.5

    worktree_count = 0
    for p in paths_to_check:
        if "-wtrees/" in p or "/worktrees/" in p or "/.worktrees/" in p:
            worktree_count += 1

    ratio = worktree_count / len(paths_to_check)
    # All worktree = 0.1 (safe), none = 0.9 (canonical/risky)
    return 0.1 + (1 - ratio) * 0.8


def _score_familiarity(command: str, audit_log_path: Path | None) -> float:
    """Score based on how often this command pattern has been allowed before."""
    if not audit_log_path or not audit_log_path.exists():
        return 0.5  # Unknown = medium risk

    events = read_audit_log(audit_log_path)
    if not events:
        return 0.5

    # Extract command prefix (first word)
    parts = command.split()
    prefix = parts[0] if parts else command

    matching_allows = sum(
        1
        for e in events
        if e.get("final_decision") == "allow"
        and e.get("command", "").startswith(prefix)
    )
    matching_denies = sum(
        1
        for e in events
        if e.get("final_decision") == "deny" and e.get("command", "").startswith(prefix)
    )

    total = matching_allows + matching_denies
    if total == 0:
        return 0.5

    # More allows = lower risk, more denies = higher risk
    # Scale: 0 denies = 0.1, all denies = 0.9
    deny_ratio = matching_denies / total
    return 0.1 + deny_ratio * 0.8


# ============================================================================
# Convenience Functions
# ============================================================================


def is_read_operation(command: str) -> bool:
    """Check if command is a read-only operation."""
    for pattern, _ in TIER_1_PATTERNS:
        if re.match(pattern, command, re.IGNORECASE):
            return True
    return False


def is_destructive_pattern(command: str) -> bool:
    """Check if command contains destructive patterns."""
    for pattern, _ in TIER_4_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False

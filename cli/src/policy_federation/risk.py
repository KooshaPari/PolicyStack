"""Risk scoring engine for policy ask decisions."""
from __future__ import annotations

from pathlib import Path

from .runtime_artifacts import read_audit_log

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
        1 for e in events
        if e.get("final_decision") == "allow" and e.get("command", "").startswith(prefix)
    )
    matching_denies = sum(
        1 for e in events
        if e.get("final_decision") == "deny" and e.get("command", "").startswith(prefix)
    )

    total = matching_allows + matching_denies
    if total == 0:
        return 0.5

    # More allows = lower risk, more denies = higher risk
    # Scale: 0 denies = 0.1, all denies = 0.9
    deny_ratio = matching_denies / total
    return 0.1 + deny_ratio * 0.8

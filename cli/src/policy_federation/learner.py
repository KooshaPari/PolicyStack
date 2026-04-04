"""Audit-driven policy learning: suggest rules from decision patterns."""
from __future__ import annotations

import datetime
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .runtime_artifacts import filter_audit_events, read_audit_log


@dataclass
class RuleSuggestion:
    id: str
    description: str
    effect: str  # allow or deny
    actions: list[str]
    command_patterns: list[str]
    cwd_patterns: list[str]
    confidence: float
    evidence_count: int
    sample_commands: list[str] = field(default_factory=list)


def _extract_command_prefix(command: str) -> str:
    """Extract a generalizable command prefix for clustering."""
    parts = command.split()
    if not parts:
        return command
    # For git commands, use first two words (git commit, git push, etc.)
    if parts[0] == "git" and len(parts) > 1:
        return f"git {parts[1]}"
    # For tool commands with subcommands
    if parts[0] in ("cargo", "npm", "bun", "pnpm", "uv", "pip", "go", "ruff", "task") and len(parts) > 1:
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def _extract_cwd_pattern(cwd: str) -> str:
    """Generalize a cwd into a pattern for rule matching."""
    if not cwd:
        return "*"
    # Detect worktree paths
    for marker in ("-wtrees/", "/.worktrees/", "/worktrees/", "/PROJECT-wtrees/"):
        idx = cwd.find(marker)
        if idx >= 0:
            base = cwd[:idx + len(marker)]
            return base + "*"
    # Canonical repo path - keep as-is
    return cwd


def _make_rule_id(prefix: str, effect: str, index: int) -> str:
    """Generate a rule ID from command prefix."""
    safe = re.sub(r"[^a-z0-9]+", "-", prefix.lower()).strip("-")
    return f"auto-{effect}-{safe}-{index:03d}"


def analyze_audit(
    audit_log_path: Path,
    *,
    since: datetime.datetime | None = None,
    min_cluster_size: int = 5,
    min_confidence: float = 0.8,
) -> list[RuleSuggestion]:
    """Analyze audit log and generate rule suggestions."""
    events = read_audit_log(audit_log_path)
    if since:
        events = filter_audit_events(events, since=since)

    # Only analyze ask and allow decisions (deny is intentional)
    relevant = [e for e in events if e.get("final_decision") in ("ask", "allow")]
    if not relevant:
        return []

    # Cluster by command prefix + cwd pattern
    clusters: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in relevant:
        cmd = event.get("command", "")
        cwd = event.get("cwd", "")
        prefix = _extract_command_prefix(cmd)
        cwd_pat = _extract_cwd_pattern(cwd)
        clusters[(prefix, cwd_pat)].append(event)

    suggestions: list[RuleSuggestion] = []
    idx = 0
    for (prefix, cwd_pat), cluster_events in sorted(clusters.items(), key=lambda x: -len(x[1])):
        if len(cluster_events) < min_cluster_size:
            continue

        # Count decisions
        decisions = Counter(e.get("final_decision") for e in cluster_events)
        total = sum(decisions.values())

        # Determine dominant decision
        dominant = decisions.most_common(1)[0]
        consistency = dominant[1] / total

        if consistency < min_confidence:
            continue

        dominant_decision = dominant[0]
        # If dominant is "ask", suggest "allow" (user likely wants to stop being asked)
        # If dominant is "allow" (from delegation), suggest explicit "allow" rule
        suggested_effect = "allow" if dominant_decision in ("ask", "allow") else "deny"

        # Determine action from events
        actions = list({e.get("action", "exec") for e in cluster_events})

        # Collect sample commands
        samples = list({e.get("command", "") for e in cluster_events[:5]})

        suggestion = RuleSuggestion(
            id=_make_rule_id(prefix, suggested_effect, idx),
            description=f"Auto-suggested: {suggested_effect} '{prefix}*' commands ({len(cluster_events)} occurrences, {consistency:.0%} consistent)",
            effect=suggested_effect,
            actions=actions,
            command_patterns=[f"{prefix}*"],
            cwd_patterns=[cwd_pat] if cwd_pat != "*" else [],
            confidence=round(consistency, 3),
            evidence_count=len(cluster_events),
            sample_commands=samples,
        )
        suggestions.append(suggestion)
        idx += 1

    return suggestions


def suggestions_to_yaml(suggestions: list[RuleSuggestion], priority: int = 85) -> str:
    """Convert rule suggestions to a YAML policy document."""
    rules = []
    for s in suggestions:
        rule: dict = {
            "id": s.id,
            "description": s.description,
            "priority": priority,
            "effect": s.effect,
            "actions": s.actions,
            "match": {},
        }
        if s.command_patterns:
            rule["match"]["command_patterns"] = s.command_patterns
        if s.cwd_patterns:
            rule["match"]["cwd_patterns"] = s.cwd_patterns

        # Add evidence as a comment-friendly field
        rule["_evidence"] = {
            "count": s.evidence_count,
            "confidence": s.confidence,
            "samples": s.sample_commands[:3],
        }
        rules.append(rule)

    doc = {
        "version": "1.0",
        "id": f"suggestions/auto-{datetime.date.today().isoformat()}",
        "scope": "repo",
        "merge": {"strategy": "append_unique"},
        "_generated": {
            "by": "policyctl learn",
            "at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "policy": {
            "authorization": {
                "rules": rules,
            },
        },
    }
    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)


def write_suggestions(
    suggestions: list[RuleSuggestion],
    output_dir: Path,
    priority: int = 85,
) -> Path:
    """Write suggestions to a YAML file in the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"auto-{datetime.date.today().isoformat()}.yaml"
    output_path = output_dir / filename
    content = suggestions_to_yaml(suggestions, priority=priority)
    output_path.write_text(content, encoding="utf-8")
    return output_path

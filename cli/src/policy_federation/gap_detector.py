"""Policy gap detection: find missing rules, dead rules, and conflicts."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from .authorization import normalize_authorization_rules
from .resolver import resolve
from .runtime_artifacts import read_audit_log


@dataclass
class GapReport:
    high_frequency_asks: list[dict] = field(default_factory=list)
    no_rule_matches: list[dict] = field(default_factory=list)
    dead_rules: list[dict] = field(default_factory=list)
    priority_conflicts: list[dict] = field(default_factory=list)


def detect_gaps(
    *,
    audit_log_path: Path,
    repo_root: Path,
    harness: str = "claude-code",
    repo: str = "",
    task_domain: str = "devops",
    task_instance: str | None = None,
    task_overlay: str | None = None,
    min_ask_frequency: int = 3,
) -> GapReport:
    """Analyze audit logs and resolved policy to detect gaps."""
    report = GapReport()
    events = read_audit_log(audit_log_path)

    if not events:
        return report

    # 1. High-frequency asks
    ask_events = [e for e in events if e.get("final_decision") == "ask"]
    ask_commands: Counter[str] = Counter()
    for e in ask_events:
        cmd = e.get("command", "")
        # Generalize: first word or first two words
        parts = cmd.split()
        prefix = " ".join(parts[:2]) if len(parts) > 1 else (parts[0] if parts else cmd)
        ask_commands[prefix] += 1

    for prefix, count in ask_commands.most_common():
        if count >= min_ask_frequency:
            report.high_frequency_asks.append({
                "command_prefix": prefix,
                "count": count,
                "severity": "HIGH" if count > 10 else "MEDIUM",
                "suggestion": f"Consider adding allow rule for '{prefix}*'",
            })

    # 2. Commands matching no explicit rule (falling to defaults)
    try:
        resolved = resolve(
            repo_root=repo_root,
            harness=harness,
            repo=repo,
            task_domain=task_domain,
            task_instance=task_instance,
            task_overlay=task_overlay,
        )
        policy = resolved["policy"]
        _, rules = normalize_authorization_rules(policy)

        # Check each unique command from audit against rules
        unique_commands: defaultdict[tuple[str, str], int] = defaultdict(int)
        for e in events:
            cmd = e.get("command", "")
            action = e.get("action", "exec")
            unique_commands[(action, cmd)] += 1

        rule_match_counts: dict[str, int] = {r.rule_id: 0 for r in rules}

        for (action, cmd), count in unique_commands.items():
            matched = False
            for rule in rules:
                if action not in rule.actions:
                    continue
                if rule.command_patterns:
                    if any(fnmatch(cmd, p) for p in rule.command_patterns):
                        matched = True
                        rule_match_counts[rule.rule_id] = rule_match_counts.get(rule.rule_id, 0) + count
                        break

            if not matched and count >= min_ask_frequency:
                report.no_rule_matches.append({
                    "action": action,
                    "command": cmd,
                    "count": count,
                    "severity": "MEDIUM",
                    "suggestion": f"No explicit rule matches '{cmd}' (seen {count} times)",
                })

        # 3. Dead rules (rules with zero audit matches)
        for rule in rules:
            if rule_match_counts.get(rule.rule_id, 0) == 0:
                report.dead_rules.append({
                    "rule_id": rule.rule_id,
                    "effect": rule.effect,
                    "severity": "LOW",
                    "suggestion": f"Rule '{rule.rule_id}' has 0 matches in audit log - verify still needed",
                })

        # 4. Priority conflicts (multiple rules at same priority with different effects)
        priority_groups: dict[int, list] = defaultdict(list)
        for rule in rules:
            priority_groups[rule.priority].append(rule)

        for priority, group in priority_groups.items():
            effects = {r.effect for r in group}
            if len(effects) > 1:
                report.priority_conflicts.append({
                    "priority": priority,
                    "rules": [{"id": r.rule_id, "effect": r.effect} for r in group],
                    "severity": "MEDIUM",
                    "suggestion": f"Priority {priority} has conflicting effects: {effects}",
                })

    except Exception:
        pass  # If resolution fails, skip rule analysis

    return report


def format_gap_report(report: GapReport) -> str:
    """Format a gap report as human-readable text."""
    lines = ["# Policy Gap Report", ""]

    if report.high_frequency_asks:
        lines.append("## High-Frequency Ask Commands")
        for item in report.high_frequency_asks:
            lines.append(f"  {item['severity']}: {item['count']}x asks for '{item['command_prefix']}*' - {item['suggestion']}")
        lines.append("")

    if report.no_rule_matches:
        lines.append("## Commands With No Explicit Rule")
        for item in report.no_rule_matches:
            lines.append(f"  {item['severity']}: '{item['command']}' ({item['count']}x) - {item['suggestion']}")
        lines.append("")

    if report.dead_rules:
        lines.append("## Dead Rules (Zero Matches)")
        for item in report.dead_rules:
            lines.append(f"  {item['severity']}: {item['rule_id']} ({item['effect']}) - {item['suggestion']}")
        lines.append("")

    if report.priority_conflicts:
        lines.append("## Priority Conflicts")
        for item in report.priority_conflicts:
            rule_desc = ", ".join(f"{r['id']}={r['effect']}" for r in item["rules"])
            lines.append(f"  {item['severity']}: Priority {item['priority']}: {rule_desc}")
        lines.append("")

    if not any([report.high_frequency_asks, report.no_rule_matches, report.dead_rules, report.priority_conflicts]):
        lines.append("No gaps detected.")

    return "\n".join(lines)

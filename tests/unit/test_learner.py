"""Tests for audit-driven policy learning."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import yaml

import support  # noqa: F401 -- setup sys.path

from policy_federation.learner import (
    RuleSuggestion,
    _extract_command_prefix,
    analyze_audit,
    suggestions_to_yaml,
)


def _write_audit(path: Path, events: list[dict]) -> None:
    with path.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


class TestAnalyzeAudit:
    def test_empty_log(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            audit_path = Path(f.name)
        suggestions = analyze_audit(audit_path)
        assert suggestions == []
        audit_path.unlink()

    def test_generates_suggestion_for_repeated_asks(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10):
                f.write(
                    json.dumps({
                        "run_id": f"r{i}",
                        "action": "exec",
                        "command": f"ls -la /some/path/{i}",
                        "cwd": "/repos/project-wtrees/feat/",
                        "final_decision": "ask",
                    })
                    + "\n"
                )
            audit_path = Path(f.name)

        suggestions = analyze_audit(audit_path, min_cluster_size=5)
        assert len(suggestions) > 0
        assert suggestions[0].effect == "allow"
        assert "ls*" in suggestions[0].command_patterns[0]
        audit_path.unlink()

    def test_respects_min_cluster_size(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(3):
                f.write(
                    json.dumps({
                        "run_id": f"r{i}",
                        "action": "exec",
                        "command": "rare-cmd",
                        "final_decision": "ask",
                    })
                    + "\n"
                )
            audit_path = Path(f.name)

        suggestions = analyze_audit(audit_path, min_cluster_size=5)
        assert len(suggestions) == 0
        audit_path.unlink()

    def test_respects_min_confidence(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Mixed decisions = low confidence
            for i in range(10):
                decision = "ask" if i % 2 == 0 else "allow"
                f.write(
                    json.dumps({
                        "run_id": f"r{i}",
                        "action": "exec",
                        "command": f"mixed-cmd {i}",
                        "final_decision": decision,
                    })
                    + "\n"
                )
            audit_path = Path(f.name)

        suggestions = analyze_audit(
            audit_path, min_cluster_size=5, min_confidence=0.9
        )
        assert len(suggestions) == 0
        audit_path.unlink()


class TestSuggestionsToYaml:
    def test_generates_valid_yaml(self) -> None:
        suggestions = [
            RuleSuggestion(
                id="auto-allow-ls-001",
                description="Auto-suggested: allow 'ls*'",
                effect="allow",
                actions=["exec"],
                command_patterns=["ls*"],
                cwd_patterns=[],
                confidence=0.95,
                evidence_count=20,
                sample_commands=["ls -la", "ls /tmp"],
            ),
        ]
        output = suggestions_to_yaml(suggestions)
        parsed = yaml.safe_load(output)
        assert parsed["version"] == "1.0"
        assert len(parsed["policy"]["authorization"]["rules"]) == 1
        assert parsed["policy"]["authorization"]["rules"][0]["effect"] == "allow"


class TestExtractCommandPrefix:
    def test_git_commands(self) -> None:
        assert _extract_command_prefix("git commit -m test") == "git commit"
        assert _extract_command_prefix("git push origin main") == "git push"

    def test_simple_commands(self) -> None:
        assert _extract_command_prefix("ls -la /tmp") == "ls"
        assert _extract_command_prefix("cat file.txt") == "cat"

    def test_tool_commands(self) -> None:
        assert _extract_command_prefix("cargo test --all") == "cargo test"
        assert _extract_command_prefix("uv run pytest") == "uv run"

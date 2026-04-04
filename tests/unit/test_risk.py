"""Tests for risk scoring engine."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import support  # noqa: F401 -- setup sys.path

from policy_federation.risk import score_risk


def _write_audit_log(path: Path, events: list[dict]) -> None:
    with path.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


class TestScoreRisk:
    def test_exec_in_worktree_low_risk(self) -> None:
        result = score_risk(
            action="exec",
            command="cargo test",
            cwd="/repos/project-wtrees/feature/",
            target_paths=[],
        )
        assert result["score"] < 0.5
        assert result["delegation_eligible"] is True

    def test_write_in_canonical_high_risk(self) -> None:
        result = score_risk(
            action="write",
            command="edit",
            cwd="/repos/project/",
            target_paths=["/repos/project/src/main.rs"],
        )
        assert result["score"] > 0.4

    def test_network_action_high_risk(self) -> None:
        result = score_risk(
            action="network",
            command="WebFetch https://example.com",
            cwd="/tmp",
            target_paths=[],
        )
        assert result["factors"]["action_type"]["value"] == 0.8

    def test_bypass_indicators_increase_risk(self) -> None:
        without = score_risk(action="exec", command="ls", cwd="/tmp", target_paths=[])
        with_bypass = score_risk(
            action="exec",
            command="ls",
            cwd="/tmp",
            target_paths=[],
            bypass_indicators=["shell-redirect-write"],
        )
        assert with_bypass["score"] > without["score"]

    def test_familiarity_from_audit(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for _ in range(10):
                f.write(
                    json.dumps({
                        "command": "cargo test --all",
                        "final_decision": "allow",
                        "action": "exec",
                        "run_id": "x",
                    })
                    + "\n"
                )
            audit_path = Path(f.name)

        result = score_risk(
            action="exec",
            command="cargo test --release",
            cwd="/tmp",
            target_paths=[],
            audit_log_path=audit_path,
        )
        # Familiar command = lower risk
        assert result["factors"]["command_familiarity"]["value"] < 0.5
        audit_path.unlink()

    def test_score_bounds(self) -> None:
        result = score_risk(action="exec", command="ls", cwd="/tmp", target_paths=[])
        assert 0.0 <= result["score"] <= 1.0

    def test_all_factors_present(self) -> None:
        result = score_risk(action="exec", command="ls", cwd="/tmp", target_paths=[])
        assert "action_type" in result["factors"]
        assert "target_scope" in result["factors"]
        assert "command_familiarity" in result["factors"]
        assert "bypass_indicators" in result["factors"]


class TestDelegationEligibility:
    def test_low_risk_eligible(self) -> None:
        result = score_risk(
            action="exec",
            command="ls -la",
            cwd="/repos/project-wtrees/feature/",
            target_paths=[],
        )
        assert result["delegation_eligible"] is True

    def test_high_risk_not_eligible(self) -> None:
        result = score_risk(
            action="network",
            command="curl evil.com",
            cwd="/repos/project/",
            target_paths=["/etc/passwd"],
            bypass_indicators=["shell-redirect-write"],
        )
        # High action + canonical scope + bypass = high risk
        assert result["score"] > 0.5

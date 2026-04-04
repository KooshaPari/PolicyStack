"""Tests for headless delegation engine."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import support  # noqa: F401 -- setup sys.path

from policy_federation.delegate import (
    DelegateContext,
    _parse_response,
    delegate_ask,
    render_delegate_prompt,
)


class TestDelegateContext:
    def test_render_prompt(self) -> None:
        ctx = DelegateContext(
            action="exec",
            command="git commit -m test",
            cwd="/repos/project-wtrees/feat/",
            target_paths=[],
            risk_score=0.25,
            risk_factors={"action_type": {"value": 0.2, "weight": 0.3}},
            rule_id="test-rule",
            rule_description="Test rule",
            scope_chain=["system/base"],
        )
        prompt = render_delegate_prompt(ctx)
        assert "git commit -m test" in prompt
        assert "security policy reviewer" in prompt.lower()
        assert '"decision"' in prompt


class TestDelegateAsk:
    def test_no_harness_returns_ask(self) -> None:
        ctx = DelegateContext(
            action="exec",
            command="test",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.1,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )
        with patch.dict("os.environ", {}, clear=True):
            result = delegate_ask(ctx, harness="")
        assert result.decision == "ask"
        assert "No delegate harness" in result.reasoning

    def test_unknown_harness(self) -> None:
        ctx = DelegateContext(
            action="exec",
            command="test",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.1,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )
        result = delegate_ask(ctx, harness="unknown-agent")
        assert result.decision == "ask"

    @patch("policy_federation.delegate.subprocess.run")
    def test_forge_allow_response(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout='{"decision": "allow", "reasoning": "Safe command", "confidence": 0.9}',
            returncode=0,
        )
        ctx = DelegateContext(
            action="exec",
            command="cargo test",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.2,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )
        result = delegate_ask(ctx, harness="forge")
        assert result.decision == "allow"
        assert result.confidence == 0.9
        assert "forge" in result.source

    @patch("policy_federation.delegate.subprocess.run")
    def test_cursor_deny_response(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout='{"decision": "deny", "reasoning": "Risky write", "confidence": 0.8}',
            returncode=0,
        )
        ctx = DelegateContext(
            action="write",
            command="edit",
            cwd="/repos/canonical/",
            target_paths=["/repos/canonical/src/lib.rs"],
            risk_score=0.6,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )
        result = delegate_ask(ctx, harness="cursor-agent")
        assert result.decision == "deny"
        assert "cursor-agent" in result.source

    @patch(
        "policy_federation.delegate.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_forge_not_found_fallback(self, mock_run: MagicMock) -> None:
        ctx = DelegateContext(
            action="exec",
            command="test",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.1,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )
        result = delegate_ask(ctx, harness="forge")
        assert result.decision == "ask"
        assert "not found" in result.reasoning

    @patch("policy_federation.delegate.subprocess.run")
    def test_malformed_response(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="I think this is fine",
            returncode=0,
        )
        ctx = DelegateContext(
            action="exec",
            command="test",
            cwd="/tmp",
            target_paths=[],
            risk_score=0.1,
            risk_factors={},
            rule_id=None,
            rule_description=None,
            scope_chain=[],
        )
        result = delegate_ask(ctx, harness="forge")
        assert result.decision == "ask"  # Can't parse = fallback


class TestParseResponse:
    def test_json_with_surrounding_text(self) -> None:
        output = (
            'Here is my analysis:\n'
            '{"decision": "allow", "reasoning": "safe", "confidence": 0.95}\n'
            'Done.'
        )
        result = _parse_response(output, "test:model")
        assert result.decision == "allow"
        assert result.confidence == 0.95

    def test_empty_output(self) -> None:
        result = _parse_response("", "test:model")
        assert result.decision == "ask"

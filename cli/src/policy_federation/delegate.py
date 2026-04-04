"""Headless agent delegation for policy ask decisions."""
from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from dataclasses import dataclass


@dataclass
class DelegateContext:
    action: str
    command: str
    cwd: str | None
    target_paths: list[str]
    risk_score: float
    risk_factors: dict
    rule_id: str | None
    rule_description: str | None
    scope_chain: list[str]


@dataclass
class DelegateResult:
    decision: str  # "allow" or "deny"
    reasoning: str
    source: str  # "forge:minimax-2.7-highspeed" or "cursor-agent:gemini-3-flash"
    confidence: float


def render_delegate_prompt(context: DelegateContext) -> str:
    """Render a structured prompt for the headless reviewer."""
    return textwrap.dedent(f"""\
        You are a security policy reviewer. Evaluate this command and respond with ONLY a JSON object.

        Command: {context.command}
        Action type: {context.action}
        Working directory: {context.cwd or "unknown"}
        Target paths: {json.dumps(context.target_paths)}
        Risk score: {context.risk_score}
        Risk factors: {json.dumps(context.risk_factors, indent=2)}
        Triggered rule: {context.rule_id or "default"} - {context.rule_description or "no description"}
        Policy scope chain: {json.dumps(context.scope_chain)}

        Evaluate whether this command should be ALLOWED or DENIED.
        Consider: Is this a safe operation? Does it modify critical files? Is it in a worktree (safe) or canonical repo (risky)?

        Respond with ONLY this JSON (no other text):
        {{"decision": "allow" or "deny", "reasoning": "brief explanation", "confidence": 0.0 to 1.0}}
    """)


def delegate_ask(context: DelegateContext, harness: str | None = None) -> DelegateResult:
    """Route an ask decision to a headless agent for review."""
    harness = harness or os.environ.get("POLICY_DELEGATE_HARNESS", "")

    if not harness:
        return DelegateResult(decision="ask", reasoning="No delegate harness configured", source="none", confidence=0.0)

    prompt = render_delegate_prompt(context)

    try:
        if harness == "forge":
            return _invoke_forge(prompt)
        elif harness == "cursor-agent":
            return _invoke_cursor(prompt)
        else:
            return DelegateResult(decision="ask", reasoning=f"Unknown delegate harness: {harness}", source=harness, confidence=0.0)
    except Exception as e:
        return DelegateResult(decision="ask", reasoning=f"Delegation failed: {e}", source=harness, confidence=0.0)


def _invoke_forge(prompt: str) -> DelegateResult:
    """Invoke forge CLI with minimax-2.7-highspeed model."""
    try:
        result = subprocess.run(
            ["forge", "--model", "minimax-2.7-highspeed", "--no-interactive", "-p", prompt],
            capture_output=True, text=True, timeout=30,
        )
        return _parse_response(result.stdout, "forge:minimax-2.7-highspeed")
    except FileNotFoundError:
        return DelegateResult(decision="ask", reasoning="forge CLI not found", source="forge", confidence=0.0)
    except subprocess.TimeoutExpired:
        return DelegateResult(decision="deny", reasoning="forge timed out", source="forge", confidence=0.5)


def _invoke_cursor(prompt: str) -> DelegateResult:
    """Invoke cursor-agent CLI with gemini-3-flash model."""
    try:
        result = subprocess.run(
            ["cursor-agent", "--model", "gemini-3-flash", "--no-interactive", "-p", prompt],
            capture_output=True, text=True, timeout=30,
        )
        return _parse_response(result.stdout, "cursor-agent:gemini-3-flash")
    except FileNotFoundError:
        return DelegateResult(decision="ask", reasoning="cursor-agent CLI not found", source="cursor-agent", confidence=0.0)
    except subprocess.TimeoutExpired:
        return DelegateResult(decision="deny", reasoning="cursor-agent timed out", source="cursor-agent", confidence=0.5)


def _parse_response(output: str, source: str) -> DelegateResult:
    """Parse JSON response from headless agent."""
    if not output.strip():
        return DelegateResult(decision="ask", reasoning="Empty response from delegate", source=source, confidence=0.0)

    # Try to extract JSON from response (agent may include extra text)
    json_match = re.search(r'\{[^{}]*"decision"[^{}]*\}', output, re.DOTALL)
    if not json_match:
        return DelegateResult(decision="ask", reasoning="Could not parse delegate response", source=source, confidence=0.0)

    try:
        data = json.loads(json_match.group())
        decision = data.get("decision", "ask")
        if decision not in ("allow", "deny"):
            decision = "ask"
        return DelegateResult(
            decision=decision,
            reasoning=data.get("reasoning", "no reasoning provided"),
            source=source,
            confidence=float(data.get("confidence", 0.5)),
        )
    except (json.JSONDecodeError, ValueError):
        return DelegateResult(decision="ask", reasoning="Malformed JSON from delegate", source=source, confidence=0.0)

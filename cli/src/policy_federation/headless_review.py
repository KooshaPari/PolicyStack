"""Headless reviewer integration for ambiguous policy decisions."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from shutil import which
from pathlib import Path

from .constants import (
    DEFAULT_REVIEW_BIN,
    DEFAULT_REVIEW_MODEL,
    DEFAULT_FALLBACK_REVIEW_BIN,
    DEFAULT_FALLBACK_REVIEW_MODEL,
)


REVIEW_DECISIONS = {"allow", "deny", "ask"}


def _reviewer_is_available(reviewer_bin: str) -> bool:
    candidate = Path(reviewer_bin).expanduser()
    if candidate.exists():
        return os.access(candidate, os.X_OK)
    return which(reviewer_bin) is not None




def _build_review_request(
    *,
    action: str,
    command: str | None,
    cwd: str | None,
    actor: str | None,
    target_paths: list[str] | None,
    policy_decision: str,
    policy_reason: str,
    matched_rules: list[dict],
) -> str:
    """Build a compact review request that asks Codex to arbitrate the decision."""
    payload = {
        "action": action,
        "command": command,
        "cwd": cwd,
        "actor": actor,
        "target_paths": target_paths or [],
        "policy_decision": policy_decision,
        "policy_reason": policy_reason,
        "matched_rules": matched_rules,
    }
    return (
        "You are a headless policy reviewer for a local developer automation system.\n"
        "Return JSON only with keys decision and reason, plus optional confidence.\n"
        "decision must be one of allow, deny, or ask.\n"
        "Use the supplied policy context to decide whether the command should be allowed,\n"
        "denied, or left as ask without requiring manual intervention.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
    )


def _extract_json_from_markdown(text: str) -> dict | None:
    """Extract JSON object from markdown code blocks or raw text."""
    # Try raw JSON first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try matching ```json ... ```
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try matching ``` ... ```
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _run_reviewer_binary(
    *,
    reviewer_bin: str,
    model: str,
    review_cwd: Path,
    request_text: str,
) -> dict:
    """Execute a specific reviewer binary and return its result."""
    if not _reviewer_is_available(reviewer_bin):
        return {
            "decision": "ask",
            "reason": f"{reviewer_bin} reviewer unavailable",
            "review_error": f"binary not found: {reviewer_bin}",
        }

    is_codex = "codex" in Path(reviewer_bin).name.lower()
    is_droid = "droid" in Path(reviewer_bin).name.lower()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {"type": "string", "enum": sorted(REVIEW_DECISIONS)},
            "reason": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["decision", "reason"],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        schema_path = Path(tmpdir) / "review-schema.json"
        output_path = Path(tmpdir) / "review-output.json"
        schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

        cmd: list[str] = [reviewer_bin, "exec", "--model", model]

        if is_codex:
            cmd.extend(
                [
                    "--sandbox",
                    "read-only",
                    "--ephemeral",
                    "--cd",
                    str(review_cwd),
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    request_text,
                ]
            )
        elif is_droid:
            # Droid doesn't support the same output flags, we'll capture stdout
            cmd.extend(["--cwd", str(review_cwd), request_text])
        else:
            # Generic fallback
            cmd.append(request_text)

        completed = subprocess.run(
            cmd,
            cwd=str(review_cwd),
            env=os.environ.copy(),
            check=False,
            text=True,
            capture_output=True,
        )

        raw = ""
        if is_codex:
            if completed.returncode == 0 and output_path.exists():
                raw = output_path.read_text(encoding="utf-8").strip()
        else:
            raw = completed.stdout.strip()

        if not raw:
            return {
                "decision": "ask",
                "reason": f"{reviewer_bin} review failed",
                "review_error": completed.stderr.strip() or completed.stdout.strip() or "no output",
                "review_command": cmd,
            }

        payload = _extract_json_from_markdown(raw) if not is_codex else None
        if is_codex:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = None

        if not payload:
            return {
                "decision": "ask",
                "reason": f"{reviewer_bin} returned invalid JSON",
                "review_error": raw[:500],
            }

        decision = payload.get("decision")
        reason = payload.get("reason") or f"{reviewer_bin} returned no reason"
        if decision not in REVIEW_DECISIONS:
            return {
                "decision": "ask",
                "reason": f"{reviewer_bin} returned unsupported decision: {decision}",
                "review_error": raw[:500],
            }

        normalized: dict = {
            "decision": decision,
            "reason": reason,
        }
        if "confidence" in payload:
            normalized["confidence"] = payload["confidence"]
        normalized["raw"] = payload
        normalized["reviewer"] = reviewer_bin
        return normalized


def run_headless_review(
    *,
    repo_root: Path,
    action: str,
    command: str | None,
    cwd: str | None,
    actor: str | None,
    target_paths: list[str] | None,
    policy_decision: str,
    policy_reason: str,
    matched_rules: list[dict],
) -> dict:
    """Run Codex/Droid as a non-interactive reviewer and return a normalized decision."""
    request_text = _build_review_request(
        action=action,
        command=command,
        cwd=cwd,
        actor=actor,
        target_paths=target_paths,
        policy_decision=policy_decision,
        policy_reason=policy_reason,
        matched_rules=matched_rules,
    )

    # Try primary reviewer
    primary_bin = os.environ.get("POLICY_REVIEW_BIN", DEFAULT_REVIEW_BIN)
    primary_model = os.environ.get("POLICY_REVIEW_MODEL", DEFAULT_REVIEW_MODEL)
    review_cwd = Path(cwd or repo_root)

    if not review_cwd.exists() or not review_cwd.is_dir():
        return {
            "decision": "ask",
            "reason": "review directory invalid",
            "review_error": f"review cwd does not exist or is not a directory: {review_cwd}",
        }

    result = _run_reviewer_binary(
        reviewer_bin=primary_bin,
        model=primary_model,
        review_cwd=review_cwd,
        request_text=request_text,
    )

    if result["decision"] != "ask" or "unavailable" not in result.get("review_error", ""):
        # If it returned a firm allow/deny, or it actually ran but returned ask, return it
        if not result.get("review_error"):
            return result
        # If it had an error but not because it was "unavailable" (e.g. usage limit), return it
        # However, if it's an auth error or usage limit, we might want to fallback.
        # Let's check for common failure modes that warrant fallback.
        err = result.get("review_error", "").lower()
        if not any(x in err for x in ["usage limit", "401", "unauthorized", "refresh token"]):
            return result

    # Try fallback reviewer
    fallback_bin = os.environ.get("POLICY_FALLBACK_REVIEW_BIN", DEFAULT_FALLBACK_REVIEW_BIN)
    fallback_model = os.environ.get("POLICY_FALLBACK_REVIEW_MODEL", DEFAULT_FALLBACK_REVIEW_MODEL)

    if fallback_bin and fallback_bin != primary_bin:
        fallback_result = _run_reviewer_binary(
            reviewer_bin=fallback_bin,
            model=fallback_model,
            review_cwd=review_cwd,
            request_text=request_text,
        )
        if fallback_result["decision"] != "ask" or not fallback_result.get("review_error"):
            fallback_result["primary_error"] = result.get("review_error")
            return fallback_result

    return result

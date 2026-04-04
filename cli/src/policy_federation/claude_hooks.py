"""Claude Code hook helpers for policy-enforced tool gating."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

from .constants import ASK_MODE_REVIEW
from .interceptor import intercept_command
from .runtime_context import infer_repo_name_from_cwd


READ_ONLY_TOOLS = {"Glob", "Grep", "LS", "Read"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
NETWORK_TOOLS = {"WebFetch", "WebSearch"}
MANAGED_TOOLS = {"Bash", *WRITE_TOOLS, *NETWORK_TOOLS}

# Patterns that indicate a Bash command is performing file writes
# (bypassing the Write tool action classification).
_WRITE_VIA_EXEC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "python-file-write",
        re.compile(
            r"python[23]?\s+-c\s+.*(?:open|write_text|write_bytes|Path.*write)",
            re.DOTALL,
        ),
    ),
    ("shell-redirect-write", re.compile(r"(?:^|&&|;|\|)\s*[^2]?[>]\s*/", re.MULTILINE)),
    ("tee-write", re.compile(r"\btee\b")),
    ("dd-write", re.compile(r"\bdd\b.*\bof=")),
    ("heredoc-write", re.compile(r'<<\s*[\'"]?EOF')),
    ("perl-file-write", re.compile(r"perl\s+-[ep].*(?:open|>)")),
    ("ruby-file-write", re.compile(r"ruby\s+-e.*(?:File\.write|open.*w)")),
    ("node-file-write", re.compile(r"node\s+-e.*(?:writeFile|createWriteStream)")),
    ("sed-inline-write", re.compile(r"\bsed\s+-i\b")),
]

# Patterns for detecting write commands inside subshell expansions
_SUBSHELL_WRITE = re.compile(
    r"(?:\$\(|`)"  # subshell start: $( or backtick
    r"[^)]*"  # content (non-greedy for $())
    r"(?:\b(?:sed\s+-i|cp|mv|tee|dd|install)\b)",
)

# Safe stderr/stdout redirects that are NOT file writes
_SAFE_REDIRECT = re.compile(r"[12]>&[12]|[12]>/dev/null|>&/dev/null")

# Protected env vars that must not be overridden via command prefixes
_PROTECTED_ENV_VARS = frozenset({
    "POLICY_REPO",
    "POLICY_TASK_DOMAIN",
    "POLICY_TASK_INSTANCE",
    "POLICY_TASK_OVERLAY",
    "POLICY_ACTOR",
    "POLICY_ASK_MODE",
    "POLICY_SIDECAR_PATH",
    "POLICY_AUDIT_LOG_PATH",
})

# Patterns for env var overrides as command prefixes:
#   VAR=value cmd ...
#   env VAR=value cmd ...
#   export VAR=value; cmd ...  (also catches export VAR=value && cmd)
_ENV_PREFIX_PATTERN = re.compile(
    r"(?:^|&&|;)\s*(?:env\s+|export\s+)?"
    r"(POLICY_\w+)=",
    re.MULTILINE,
)


def _detect_env_override(command: str) -> list[str]:
    """Detect attempts to override POLICY_* env vars via command prefixes.

    Returns a list of protected variable names that were overridden.
    """
    found: list[str] = []
    for match in _ENV_PREFIX_PATTERN.finditer(command):
        var_name = match.group(1)
        if var_name in _PROTECTED_ENV_VARS:
            found.append(var_name)
    return found


def _strip_env_overrides(command: str) -> str:
    """Strip POLICY_* env var override prefixes from a command string.

    Removes patterns like ``POLICY_REPO=evil`` or ``env POLICY_REPO=evil``
    that appear before the actual command.
    """
    # Strip leading env-var assignments (with optional env/export prefix)
    # repeatedly until none remain at the start of the command.
    cmd = command.strip()
    prefix_re = re.compile(
        r"^(?:env\s+|export\s+)?"
        r"POLICY_\w+=\S*\s*"
    )
    while prefix_re.match(cmd):
        cmd = prefix_re.sub("", cmd, count=1).strip()
    return cmd


def _normalize_bash_command(command: str) -> tuple[str, str | None]:
    """Strip cd prefix and trailing safe pipes to normalize for policy matching.

    Returns (normalized_command, effective_cwd_override).
    The effective_cwd is used as a secondary cwd signal when the command
    includes an explicit cd.
    """
    cmd = command.strip()
    effective_cwd: str | None = None

    # Strip leading 'cd /path &&' or 'cd /path;'
    cd_match = re.match(r"^cd\s+(\S+)\s*(?:&&|;)\s*(.+)$", cmd, re.DOTALL)
    if cd_match:
        effective_cwd = cd_match.group(1).strip("'\"")
        cmd = cd_match.group(2).strip()

    # Strip safe trailing pipes for matching (but keep full command for audit).
    # Only strip pipes to known-safe read-only postprocessors.
    pipe_match = re.match(
        r"^(.+?)\s*(?:2>&1\s*)?\|\s*"
        r"(?:head|tail|grep|wc|sort|uniq|less|more|cat|tr|cut|awk|sed)\b.*$",
        cmd,
        re.DOTALL,
    )
    if pipe_match:
        cmd = pipe_match.group(1).strip()

    # Strip safe stderr/stdout redirects for matching
    cmd = _SAFE_REDIRECT.sub("", cmd).strip()

    return cmd, effective_cwd


def _split_compound_command(command: str) -> list[str]:
    """Split a compound command on ``&&``, ``;``, and ``||`` separators.

    Returns individual command segments for independent pattern checking.
    Quoted strings and subshells are not deeply parsed; this is a
    best-effort split suitable for detection heuristics.
    """
    # Split on && ; || that are not inside quotes (simple heuristic)
    segments = re.split(r"\s*(?:&&|;|\|\|)\s*", command)
    return [s.strip() for s in segments if s.strip()]


def _detect_write_via_exec(command: str) -> list[str]:
    """Detect Bash commands that perform file writes (bypass write-action rules).

    Returns a list of bypass indicator names (empty if no bypass detected).
    Handles compound commands (&&, ;, ||) by checking each segment,
    and detects write commands inside subshell expansions ($(...) and backticks).
    """
    indicators: list[str] = []
    seen: set[str] = set()

    # Check each compound-command segment independently
    segments = _split_compound_command(command)
    for segment in segments:
        for name, pattern in _WRITE_VIA_EXEC_PATTERNS:
            if name not in seen and pattern.search(segment):
                indicators.append(name)
                seen.add(name)

    # Check for write commands inside subshell expansions
    if _SUBSHELL_WRITE.search(command) and "subshell-write" not in seen:
        indicators.append("subshell-write")
        seen.add("subshell-write")

    # Also check subshell contents by extracting them
    for subshell_match in re.finditer(r"\$\(([^)]+)\)", command):
        inner = subshell_match.group(1)
        for name, pattern in _WRITE_VIA_EXEC_PATTERNS:
            prefixed = f"subshell:{name}"
            if prefixed not in seen and pattern.search(inner):
                indicators.append(prefixed)
                seen.add(prefixed)

    # Check backtick subshells
    for bt_match in re.finditer(r"`([^`]+)`", command):
        inner = bt_match.group(1)
        for name, pattern in _WRITE_VIA_EXEC_PATTERNS:
            prefixed = f"subshell:{name}"
            if prefixed not in seen and pattern.search(inner):
                indicators.append(prefixed)
                seen.add(prefixed)

    return indicators


def _resolve_target_path(target_path: str, cwd: str) -> str:
    """Resolve a possibly-relative target path against the command cwd."""
    path = Path(target_path)
    if path.is_absolute():
        return str(path)
    return str((Path(cwd) / path).resolve())


def _extract_sed_target_paths(command: str, cwd: str) -> list[str]:
    """Extract sed -i target paths from a shell command."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return []

    if len(parts) < 3 or parts[0] != "sed" or "-i" not in parts:
        return []

    target_paths: list[str] = []
    for part in reversed(parts):
        if part == "sed" or part == "-i" or part.startswith("-") or part.startswith("s/"):
            continue
        target_paths.append(_resolve_target_path(part, cwd))
        break
    return target_paths


def _default_repo_name(cwd: str | None) -> str:
    if os.environ.get("POLICY_REPO"):
        return os.environ["POLICY_REPO"]
    return infer_repo_name_from_cwd(cwd)


def _default_audit_log_path() -> Path | None:
    audit_log_path = os.environ.get("POLICY_AUDIT_LOG_PATH")
    return Path(audit_log_path).expanduser() if audit_log_path else None


def _extract_request(payload: dict) -> dict | None:
    tool_name = payload.get("tool_name")
    if tool_name in READ_ONLY_TOOLS:
        return None
    if tool_name not in MANAGED_TOOLS:
        return None

    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or str(Path.cwd())

    if tool_name == "Bash":
        command = tool_input.get("command")
        if not command:
            return None

        # Detect and block POLICY_* env var overrides
        env_overrides = _detect_env_override(command)
        if env_overrides:
            command = _strip_env_overrides(command)

        # Normalize command for policy matching
        normalized_cmd, effective_cwd = _normalize_bash_command(command)
        resolved_cwd = effective_cwd or cwd

        # Check for write-via-exec bypasses
        bypass_indicators = _detect_write_via_exec(command)
        if env_overrides:
            bypass_indicators.extend(
                f"env-override:{v}" for v in env_overrides
            )
        if bypass_indicators:
            # Reclassify as a write action so write-action rules apply.
            # Extract target paths from the command where possible.
            target_paths: list[str] = []
            if "sed-inline-write" in bypass_indicators:
                target_paths.extend(_extract_sed_target_paths(command, resolved_cwd))
            # Try to extract file paths from python open() calls
            for m in re.finditer(r"open\(['\"]([^'\"]+)['\"]", command):
                target_paths.append(_resolve_target_path(m.group(1), resolved_cwd))
            # Try to extract redirect targets
            for m in re.finditer(r"(?:^|&&|;|\|)\s*[^2]?[>]+\s*(\S+)", command):
                target_paths.append(_resolve_target_path(m.group(1), resolved_cwd))
            # Try to extract tee targets
            for m in re.finditer(r"\btee\s+(?:-a\s+)?(\S+)", command):
                target_paths.append(_resolve_target_path(m.group(1), resolved_cwd))

            return {
                "action": "write",
                "command": command,
                "cwd": resolved_cwd,
                "target_paths": target_paths or [resolved_cwd],
                "bypass_indicators": bypass_indicators,
            }

        return {
            "action": "exec",
            "command": normalized_cmd,
            "cwd": resolved_cwd,
            "target_paths": [],
        }

    if tool_name in WRITE_TOOLS:
        file_path = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("notebook_path")
        )
        if not file_path:
            return None
        return {
            "action": "write",
            "command": tool_name.lower(),
            "cwd": cwd,
            "target_paths": [file_path],
        }

    if tool_name == "WebFetch":
        url = tool_input.get("url") or ""
        return {
            "action": "network",
            "command": f"WebFetch {url}".strip(),
            "cwd": cwd,
            "target_paths": [],
        }

    query = tool_input.get("query") or ""
    return {
        "action": "network",
        "command": f"WebSearch {query}".strip(),
        "cwd": cwd,
        "target_paths": [],
    }


def evaluate_claude_pretool_payload(payload: dict, repo_root: Path | None = None) -> dict:
    """Evaluate Claude hook payload and return Claude-compatible hook output."""
    request = _extract_request(payload)
    if request is None:
        return {"continue": True, "suppressOutput": True}

    cwd = request["cwd"]
    result = intercept_command(
        repo_root=repo_root or Path(__file__).resolve().parents[3],
        harness="claude-code",
        repo=_default_repo_name(cwd),
        task_domain=os.environ.get("POLICY_TASK_DOMAIN", "devops"),
        task_instance=os.environ.get("POLICY_TASK_INSTANCE"),
        task_overlay=os.environ.get("POLICY_TASK_OVERLAY"),
        action=request["action"],
        command=request["command"],
        cwd=cwd,
        actor=os.environ.get("POLICY_ACTOR") or payload.get("session_id"),
        target_paths=request["target_paths"],
        ask_mode=os.environ.get("POLICY_ASK_MODE", "fail"),
    )

    if result["final_decision"] == "allow":
        evaluation = result.get("evaluation") or {}
        headless_review = evaluation.get("headless_review")
        if headless_review:
            winning_rule = evaluation.get("winning_rule") or {}
            rule_id = winning_rule.get("id") or evaluation.get("reason", "default-allow")
            if rule_id.startswith("matched rule "):
                rule_id = rule_id[len("matched rule "):]

            reasoning = headless_review.get("reason", "No specific reasoning provided.")
            command = request.get("command", payload.get("tool_name", "unknown tool"))
            reviewer = headless_review.get("reviewer", "guardian")
            reviewer_name = "Guardian" if "codex" in reviewer.lower() else f"Guardian ({reviewer})"

            return {
                "continue": True,
                "suppressOutput": False,
                "hookSpecificOutput": f"{reviewer_name}: Reviewed and allowed {command} (Rule: {rule_id}, Reasoning: {reasoning})",
            }

        return {"continue": True, "suppressOutput": True}

    winning_rule = result["evaluation"].get("winning_rule") or {}
    reason = winning_rule.get("id") or result["policy_decision"]

    # Include guardian failure/decision in the reason
    evaluation = result.get("evaluation") or {}
    headless_review = evaluation.get("headless_review")
    guardian_suffix = ""
    if headless_review:
        if headless_review.get("review_error"):
            # Truncate and clean error for notification
            err = headless_review["review_error"]
            if "refresh token has already been used" in err or "401" in err:
                err = "Authentication required (codex login)"
            elif "usage limit" in err or "429" in err:
                err = "Usage limit hit"
            guardian_suffix = f" [Guardian Error: {err[:50]}]"
        elif headless_review.get("decision") == "ask":
            guardian_suffix = f" [Guardian Decision: ask - {headless_review.get('reason', 'Ambigious')[:50]}]"

    # Include bypass indicators in the reason when present
    bypass = request.get("bypass_indicators")
    if bypass:
        reason = f"policy-federation:{reason}{guardian_suffix} [write-via-exec:{','.join(bypass)}]"
    else:
        # Check if this is a tool that should provide a reason for the 'ask'
        command = request.get("command", "")
        if command and any(cmd in command for cmd in ["ruff", "pip", "npm", "cargo"]):
             reason = f"policy-federation:{reason}{guardian_suffix} [reason: Check for safe flags or local targets]"
        else:
             reason = f"policy-federation:{reason}{guardian_suffix}"

    # Include delegation metadata when present
    evaluation = result.get("evaluation", {})
    delegate_source = evaluation.get("delegate_source")
    if delegate_source:
        reason = f"{reason} [delegated:{delegate_source}]"

    return {
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": result["final_decision"],
            "permissionDecisionReason": reason,
        },
    }


def main() -> None:
    payload = json.load(sys.stdin)
    result = evaluate_claude_pretool_payload(payload)
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

"""Headless agent delegation for policy ask decisions.

Multi-platform policy delegation with learning, fallback chains, and tiered risk assessment.
Supports: forge, opencode, cursor, codex, droid, kilo, forgecode
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DelegateContext:
    """Context for policy delegation decision."""

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
    """Result of policy delegation."""

    decision: str  # "allow", "deny", or "ask"
    reasoning: str
    source: str  # e.g., "forge:minimax-2.7-highspeed", "local-fast", "cache"
    confidence: float


# Harness fallback chains - ordered by preference
HARNESS_FALLBACK = {
    "forge": ["opencode", "cursor", "local-fast"],
    "opencode": ["forge", "cursor", "local-fast"],
    "cursor": ["opencode", "forge", "local-fast"],
    "codex": ["opencode", "forge", "local-fast"],
    "droid": ["opencode", "forge", "local-fast"],
    "kilo": ["opencode", "forge", "local-fast"],
    "forgecode": ["forge", "opencode", "local-fast"],
    "local-fast": [],  # Terminal fallback
}

# CLI commands and models for each harness
HARNESS_CONFIG = {
    "forge": {
        "cli": "forge",
        "model": "minimax-2.7-highspeed",
        "timeout": 30,
    },
    "opencode": {
        "cli": "opencode",
        "model": "kimi-k2.5",  # Default model for opencode
        "timeout": 15,
    },
    "cursor": {
        "cli": "cursor-agent",
        "model": "gemini-3-flash",
        "timeout": 20,
    },
    "codex": {
        "cli": "codex",
        "model": "gpt-5.3-codex",
        "timeout": 20,
    },
    "droid": {
        "cli": "droid",
        "model": "factory-default",
        "timeout": 25,
    },
    "kilo": {
        "cli": "kilo",
        "model": "kilo-default",
        "timeout": 15,
    },
    "forgecode": {
        "cli": "forgecode",
        "api_url": "https://api.forgecode.dev/v1/review",
        "timeout": 20,
    },
}

# Risk patterns for local-fast evaluation
RISK_PATTERNS = {
    "read_safe": [
        r"^git\s+status",
        r"^git\s+log",
        r"^git\s+diff",
        r"^ls\s",
        r"^cat\s",
        r"^head\s",
        r"^tail\s",
        r"^grep\s",
        r"^find\s.*-type\s+f",
        r"^read\s",
    ],
    "write_low_risk": [
        r"^git\s+add\s",
        r"^git\s+commit\s",
        r"^git\s+checkout\s",
        r"^git\s+branch\s",
        r"^mkdir\s+-p\s",
        r"^touch\s",
    ],
    "write_high_risk": [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r">\s+/etc/",
        r"sudo\s",
        r"chmod\s+777\s",
        r"curl\s.*\|\s*sh",
        r"wget\s.*\|\s*sh",
    ],
}


def _get_cache_db() -> Path:
    """Get cache database path."""
    cache_dir = Path.home() / ".phenotype" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "delegate_cache.db"


def _init_cache() -> None:
    """Initialize cache database."""
    db_path = _get_cache_db()
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decision_cache (
            command_hash TEXT PRIMARY KEY,
            command_pattern TEXT,
            decision TEXT,
            source TEXT,
            confidence REAL,
            timestamp REAL,
            hit_count INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pattern ON decision_cache(command_pattern)
    """)
    conn.commit()
    conn.close()


def _get_cached_decision(command: str) -> DelegateResult | None:
    """Check for cached decision."""
    try:
        _init_cache()
        db_path = _get_cache_db()
        conn = sqlite3.connect(db_path)

        # Try exact match first
        command_hash = _hash_command(command)
        cursor = conn.execute(
            "SELECT decision, source, confidence FROM decision_cache WHERE command_hash = ? AND timestamp > ?",
            (command_hash, time.time() - 86400),  # 24h TTL
        )
        row = cursor.fetchone()
        if row:
            # Update hit count
            conn.execute(
                "UPDATE decision_cache SET hit_count = hit_count + 1 WHERE command_hash = ?",
                (command_hash,),
            )
            conn.commit()
            conn.close()
            return DelegateResult(
                decision=row[0],
                reasoning="Cached decision",
                source=f"cache:{row[1]}",
                confidence=row[2],
            )

        # Try pattern match for similar commands
        pattern = _extract_pattern(command)
        cursor = conn.execute(
            "SELECT decision, source, confidence, command_hash FROM decision_cache WHERE command_pattern = ? AND timestamp > ? ORDER BY hit_count DESC LIMIT 1",
            (pattern, time.time() - 86400),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return DelegateResult(
                decision=row[0],
                reasoning=f"Pattern match: {pattern}",
                source=f"cache-pattern:{row[1]}",
                confidence=row[2]
                * 0.9,  # Slightly reduced confidence for pattern match
            )

        return None
    except Exception:
        return None


def _cache_decision(command: str, result: DelegateResult) -> None:
    """Cache a decision result."""
    try:
        _init_cache()
        db_path = _get_cache_db()
        conn = sqlite3.connect(db_path)

        command_hash = _hash_command(command)
        pattern = _extract_pattern(command)

        conn.execute(
            """INSERT OR REPLACE INTO decision_cache 
               (command_hash, command_pattern, decision, source, confidence, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                command_hash,
                pattern,
                result.decision,
                result.source,
                result.confidence,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Fail silently - caching is best-effort


def _hash_command(command: str) -> str:
    """Create hash of command for cache key."""
    import hashlib

    return hashlib.sha256(command.encode()).hexdigest()[:16]


def _extract_pattern(command: str) -> str:
    """Extract pattern from command for fuzzy matching."""
    # Remove specific file paths, keeping only the command structure
    pattern = re.sub(r"\s+/[^\s]+", " <PATH>", command)
    pattern = re.sub(r"\s+\d+", " <NUM>", pattern)
    return pattern


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


def _local_fast_evaluate(context: DelegateContext) -> DelegateResult | None:
    """Fast local evaluation without LLM call.

    Uses pattern matching to make quick decisions on common operations.
    Returns None if can't make a confident decision locally.
    """
    command = context.command.strip()

    # Check read-safe patterns (Tier 1)
    for pattern in RISK_PATTERNS["read_safe"]:
        if re.match(pattern, command, re.IGNORECASE):
            return DelegateResult(
                decision="allow",
                reasoning=f"Read-safe operation matches: {pattern}",
                source="local-fast:read-safe",
                confidence=0.95,
            )

    # Check low-risk write patterns (Tier 2) - only in worktrees
    is_worktree = context.cwd and (
        ".worktrees" in context.cwd or "worktrees" in context.cwd
    )
    if is_worktree:
        for pattern in RISK_PATTERNS["write_low_risk"]:
            if re.match(pattern, command, re.IGNORECASE):
                return DelegateResult(
                    decision="allow",
                    reasoning=f"Low-risk git operation in worktree: {pattern}",
                    source="local-fast:worktree-safe",
                    confidence=0.90,
                )

    # Check high-risk patterns (always deny)
    for pattern in RISK_PATTERNS["write_high_risk"]:
        if re.search(pattern, command, re.IGNORECASE):
            return DelegateResult(
                decision="deny",
                reasoning=f"High-risk pattern detected: {pattern}",
                source="local-fast:risk-pattern",
                confidence=0.95,
            )

    # Can't decide locally - need delegation
    return None


def _invoke_harness(harness: str, prompt: str) -> DelegateResult:
    """Invoke a specific harness."""
    config = HARNESS_CONFIG.get(harness)
    if not config:
        return DelegateResult(
            decision="ask",
            reasoning=f"Unknown harness: {harness}",
            source=harness,
            confidence=0.0,
        )

    cli = config["cli"]
    timeout = config.get("timeout", 30)

    # Handle API-based harnesses (like forgecode)
    if "api_url" in config:
        return _invoke_api_harness(harness, prompt, config)

    # Handle CLI-based harnesses
    model = config.get("model", "default")

    # Build command - different CLIs have different argument formats
    if harness == "opencode":
        cmd = [cli, "review", "--model", model, "--non-interactive", "--prompt", prompt]
    elif harness == "codex":
        cmd = [cli, "review", "--model", model, "--json", prompt]
    elif harness == "droid":
        cmd = [cli, "check", "--policy", model, "--input", prompt]
    elif harness == "kilo":
        cmd = [cli, "review", "--mode", "fast", "--prompt", prompt]
    else:
        # Default format (forge, cursor)
        cmd = [cli, "--model", model, "--no-interactive", "-p", prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return DelegateResult(
                decision="ask",
                reasoning=f"{harness} CLI error: {result.stderr[:100]}",
                source=harness,
                confidence=0.0,
            )
        return _parse_response(result.stdout, f"{harness}:{model}")
    except FileNotFoundError:
        return DelegateResult(
            decision="ask",
            reasoning=f"{harness} CLI not found",
            source=harness,
            confidence=0.0,
        )
    except subprocess.TimeoutExpired:
        return DelegateResult(
            decision="deny",
            reasoning=f"{harness} timed out after {timeout}s",
            source=harness,
            confidence=0.5,
        )


def _invoke_api_harness(harness: str, prompt: str, config: dict) -> DelegateResult:
    """Invoke API-based harness (forgecode.dev)."""
    import urllib.error
    import urllib.request

    api_url = config["api_url"]
    timeout = config.get("timeout", 20)

    # Get API key from environment
    api_key = os.environ.get(f"{harness.upper()}_API_KEY", "")
    if not api_key:
        return DelegateResult(
            decision="ask",
            reasoning=f"{harness} API key not configured",
            source=harness,
            confidence=0.0,
        )

    try:
        data = json.dumps(
            {
                "prompt": prompt,
                "model": config.get("model", "default"),
            },
        ).encode()

        req = urllib.request.Request(
            api_url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode())
            return _parse_response(
                json.dumps(result.get("review", {})),
                f"{harness}:{config.get('model', 'api')}",
            )

    except urllib.error.URLError as e:
        return DelegateResult(
            decision="ask",
            reasoning=f"{harness} API error: {e}",
            source=harness,
            confidence=0.0,
        )
    except Exception as e:
        return DelegateResult(
            decision="ask",
            reasoning=f"{harness} failed: {e}",
            source=harness,
            confidence=0.0,
        )


def delegate_ask(
    context: DelegateContext,
    harness: str | None = None,
    use_cache: bool = True,
    use_local_fast: bool = True,
) -> DelegateResult:
    """Route an ask decision to a headless agent for review.

    Args:
        context: Decision context
        harness: Preferred harness (auto-detected if None)
        use_cache: Whether to use decision cache
        use_local_fast: Whether to use local-fast evaluator

    Returns:
        DelegateResult with decision and reasoning
    """
    # Step 1: Try local-fast evaluation (fastest path)
    if use_local_fast:
        local_result = _local_fast_evaluate(context)
        if local_result:
            if use_cache:
                _cache_decision(context.command, local_result)
            return local_result

    # Step 2: Check cache
    if use_cache:
        cached = _get_cached_decision(context.command)
        if cached:
            return cached

    # Step 3: Determine harness and fallback chain
    harness = harness or os.environ.get("POLICY_DELEGATE_HARNESS", "")

    if not harness:
        # Auto-detect based on available CLIs
        harness = _auto_detect_harness()

    if not harness:
        return DelegateResult(
            decision="ask",
            reasoning="No delegate harness configured or detected",
            source="none",
            confidence=0.0,
        )

    # Get fallback chain
    fallback_chain = [harness] + HARNESS_FALLBACK.get(harness, ["local-fast"])

    # Step 4: Try harnesses in order
    prompt = render_delegate_prompt(context)
    last_error = ""

    for h in fallback_chain:
        if h == "local-fast":
            # Already tried above, skip
            continue

        result = _invoke_harness(h, prompt)

        # If successful (not "ask" due to failure), use it
        if result.decision in ("allow", "deny") or result.confidence > 0:
            if use_cache:
                _cache_decision(context.command, result)
            return result

        # Track error for final message
        last_error = f"{h}: {result.reasoning}"

    # Step 5: All harnesses failed - ask human
    return DelegateResult(
        decision="ask",
        reasoning=f"All harnesses failed. Last: {last_error}",
        source="fallback",
        confidence=0.0,
    )


def _auto_detect_harness() -> str | None:
    """Auto-detect available harness based on installed CLIs."""
    cli_checks = [
        ("opencode", "opencode"),
        ("forge", "forge"),
        ("cursor-agent", "cursor"),
        ("codex", "codex"),
        ("droid", "droid"),
        ("kilo", "kilo"),
    ]

    for cli, harness in cli_checks:
        if _cli_available(cli):
            return harness

    return None


def _cli_available(cli: str) -> bool:
    """Check if a CLI is available in PATH."""
    try:
        subprocess.run(
            [cli, "--version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _parse_response(output: str, source: str) -> DelegateResult:
    """Parse JSON response from headless agent."""
    if not output.strip():
        return DelegateResult(
            decision="ask",
            reasoning="Empty response from delegate",
            source=source,
            confidence=0.0,
        )

    # Try to extract JSON from response (agent may include extra text)
    # Support both {"decision":...} and {"review": {"decision":...}} formats
    json_patterns = [
        r'\{[^{}]*"decision"[^{}]*\}',  # Simple JSON
        r'\{[^{}]*"review"\s*:\s*\{[^{}]*"decision"[^{}]*\}[^{}]*\}',  # Nested review
        r'\{[\s\S]*?"decision"[\s\S]*?\}',  # Multi-line JSON
    ]

    for pattern in json_patterns:
        json_match = re.search(pattern, output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())

                # Handle nested review format
                if "review" in data and isinstance(data["review"], dict):
                    data = data["review"]

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
                continue

    return DelegateResult(
        decision="ask",
        reasoning="Could not parse delegate response",
        source=source,
        confidence=0.0,
    )


def get_cache_stats() -> dict[str, Any]:
    """Get statistics about the decision cache."""
    try:
        db_path = _get_cache_db()
        conn = sqlite3.connect(db_path)

        stats = {}

        # Total entries
        cursor = conn.execute("SELECT COUNT(*) FROM decision_cache")
        stats["total_entries"] = cursor.fetchone()[0]

        # Entries by decision
        cursor = conn.execute(
            "SELECT decision, COUNT(*) FROM decision_cache GROUP BY decision",
        )
        stats["by_decision"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Hit counts
        cursor = conn.execute(
            "SELECT SUM(hit_count), AVG(hit_count), MAX(hit_count) FROM decision_cache",
        )
        row = cursor.fetchone()
        stats["total_hits"] = row[0] or 0
        stats["avg_hits"] = row[1] or 0
        stats["max_hits"] = row[2] or 0

        # Recent entries (last 24h)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM decision_cache WHERE timestamp > ?",
            (time.time() - 86400,),
        )
        stats["entries_24h"] = cursor.fetchone()[0]

        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}


def clear_cache() -> bool:
    """Clear the decision cache. Returns True on success."""
    try:
        db_path = _get_cache_db()
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM decision_cache")
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# Backward compatibility - keep old function names
_invoke_forge = lambda prompt: _invoke_harness("forge", prompt)
_invoke_cursor = lambda prompt: _invoke_harness("cursor", prompt)

"""Droid platform wrapper for PolicyStack.

Integrates with Droid agent CLI to provide policy-enforced command execution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class DroidWrapper:
    """Wrapper for Droid platform integration."""

    def __init__(self, model: str = "factory-default") -> None:
        self.model = model
        self.cli = "droid"
        self.timeout = 25

    def is_available(self) -> bool:
        """Check if Droid CLI is available."""
        try:
            subprocess.run(
                [self.cli, "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def review_command(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Review a command using Droid.

        Returns:
            Dict with 'decision' (allow/deny/ask), 'reasoning', 'confidence'
        """
        if not self.is_available():
            return {
                "decision": "ask",
                "reasoning": "Droid CLI not available",
                "confidence": 0.0,
            }

        prompt = self._build_prompt(command, context)

        try:
            result = subprocess.run(
                [
                    self.cli,
                    "check",
                    "--policy",
                    self.model,
                    "--input",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                return {
                    "decision": "ask",
                    "reasoning": f"Droid error: {result.stderr[:100]}",
                    "confidence": 0.0,
                }

            return self._parse_response(result.stdout)

        except subprocess.TimeoutExpired:
            return {
                "decision": "deny",
                "reasoning": f"Droid timed out after {self.timeout}s",
                "confidence": 0.5,
            }
        except Exception as e:
            return {
                "decision": "ask",
                "reasoning": f"Droid failed: {e}",
                "confidence": 0.0,
            }

    def _build_prompt(self, command: str, context: dict[str, Any] | None) -> str:
        """Build review prompt for Droid."""
        ctx = context or {}
        return json.dumps(
            {
                "command": command,
                "cwd": ctx.get("cwd", os.getcwd()),
                "action": ctx.get("action", "exec"),
                "target_paths": ctx.get("target_paths", []),
                "risk_score": ctx.get("risk_score", 0.5),
                "scope_chain": ctx.get("scope_chain", []),
            }
        )

    def _parse_response(self, output: str) -> dict[str, Any]:
        """Parse Droid JSON response."""
        if not output.strip():
            return {
                "decision": "ask",
                "reasoning": "Empty response from Droid",
                "confidence": 0.0,
            }

        import re

        json_match = re.search(r'\{[\s\S]*?"decision"[\s\S]*?\}', output)
        if json_match:
            try:
                data = json.loads(json_match.group())
                decision = data.get("decision", "ask")
                if decision not in ("allow", "deny"):
                    decision = "ask"
                return {
                    "decision": decision,
                    "reasoning": data.get("reasoning", "no reasoning"),
                    "confidence": float(data.get("confidence", 0.5)),
                }
            except (json.JSONDecodeError, ValueError):
                pass

        return {
            "decision": "ask",
            "reasoning": "Could not parse Droid response",
            "confidence": 0.0,
        }


def main() -> None:
    """CLI entry point for Droid wrapper."""
    import argparse

    parser = argparse.ArgumentParser(description="Droid Policy Wrapper")
    parser.add_argument("--command", required=True, help="Command to review")
    parser.add_argument("--cwd", default=os.getcwd(), help="Working directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--model", default="factory-default", help="Model to use")

    args = parser.parse_args()

    wrapper = DroidWrapper(model=args.model)
    result = wrapper.review_command(
        args.command,
        context={"cwd": args.cwd},
    )

    if args.json:
        print(json.dumps(result))
    else:
        print(result["decision"])

    sys.exit(
        0 if result["decision"] == "allow" else 1 if result["decision"] == "deny" else 2
    )


if __name__ == "__main__":
    main()

"""Cursor platform wrapper for PolicyStack.

Integrates with Cursor agent CLI to provide policy-enforced command execution.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any


class CursorWrapper:
    """Wrapper for Cursor platform integration."""

    def __init__(self, model: str = "gemini-3-flash") -> None:
        self.model = model
        self.cli = "cursor-agent"
        self.timeout = 20

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract JSON from CLI output."""
        if not text.strip():
            return None

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        match = re.search(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"```\s*(.*?)\s*```", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def is_available(self) -> bool:
        """Check if Cursor agent CLI is available."""
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
        """Review a command using Cursor."""
        if not self.is_available():
            return {
                "decision": "ask",
                "reasoning": "Cursor CLI not available",
                "confidence": 0.0,
            }

        prompt = self._build_prompt(command, context)

        try:
            result = self._run_review(prompt)
            if result.returncode != 0:
                return {
                    "decision": "ask",
                    "reasoning": f"Cursor error: {result.stderr[:100]}",
                    "confidence": 0.0,
                }

            return self._parse_response(result.stdout)

        except subprocess.TimeoutExpired:
            return {
                "decision": "deny",
                "reasoning": f"Cursor timed out after {self.timeout}s",
                "confidence": 0.5,
            }
        except Exception as e:
            return {
                "decision": "ask",
                "reasoning": f"Cursor failed: {e}",
                "confidence": 0.0,
            }

    def _run_review(self, prompt: str) -> subprocess.CompletedProcess:
        """Execute the Cursor CLI."""
        return subprocess.run(
            [
                self.cli,
                "--model",
                self.model,
                "--no-interactive",
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

    def _build_prompt(self, command: str, context: dict[str, Any] | None) -> str:
        """Build review prompt for Cursor."""
        ctx = context or {}
        return json.dumps(
            {
                "command": command,
                "cwd": ctx.get("cwd", os.getcwd()),
                "action": ctx.get("action", "exec"),
                "target_paths": ctx.get("target_paths", []),
                "risk_score": ctx.get("risk_score", 0.5),
                "scope_chain": ctx.get("scope_chain", []),
            },
        )

    def _parse_response(self, output: str) -> dict[str, Any]:
        """Parse Cursor JSON response."""
        data = self._extract_json(output)
        if not data:
            return {
                "decision": "ask",
                "reasoning": "No parseable JSON from Cursor",
                "confidence": 0.0,
            }

        if "review" in data and isinstance(data["review"], dict):
            data = data["review"]

        decision = data.get("decision", "ask")
        if decision not in ("allow", "deny"):
            decision = "ask"

        return {
            "decision": decision,
            "reasoning": data.get("reasoning", "no reasoning"),
            "confidence": float(data.get("confidence", 0.5)),
        }


def main() -> None:
    """CLI entry point for Cursor wrapper."""
    import argparse

    parser = argparse.ArgumentParser(description="Cursor Policy Wrapper")
    parser.add_argument("--command", required=True, help="Command to review")
    parser.add_argument("--cwd", default=os.getcwd(), help="Working directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--model", default="gemini-3-flash", help="Model to use")

    args = parser.parse_args()

    wrapper = CursorWrapper(model=args.model)
    result = wrapper.review_command(
        args.command,
        context={"cwd": args.cwd},
    )

    if args.json:
        print(json.dumps(result))
    else:
        print(f"{result['decision']}: {result['reasoning']}")

    sys.exit(
        0
        if result["decision"] == "allow"
        else 1
        if result["decision"] == "deny"
        else 2,
    )


if __name__ == "__main__":
    main()

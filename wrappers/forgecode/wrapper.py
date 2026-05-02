"""ForgeCode platform wrapper for PolicyStack.

Integrates with forgecode.dev API to provide policy-enforced command execution.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


class ForgeCodeWrapper:
    """Wrapper for ForgeCode (forgecode.dev) platform integration."""

    def __init__(self, model: str = "forge-default") -> None:
        self.model = model
        self.api_url = "https://api.forgecode.dev/v1/review"
        self.timeout = 20

    def is_available(self) -> bool:
        """Check if ForgeCode API key is configured."""
        return bool(os.environ.get("FORGECODE_API_KEY"))

    def review_command(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Review a command using ForgeCode API.

        Returns:
            Dict with 'decision' (allow/deny/ask), 'reasoning', 'confidence'
        """
        api_key = os.environ.get("FORGECODE_API_KEY")
        if not api_key:
            return {
                "decision": "ask",
                "reasoning": "ForgeCode API key not configured (FORGECODE_API_KEY)",
                "confidence": 0.0,
            }

        ctx = context or {}
        payload = {
            "command": command,
            "cwd": ctx.get("cwd", os.getcwd()),
            "action": ctx.get("action", "exec"),
            "target_paths": ctx.get("target_paths", []),
            "risk_score": ctx.get("risk_score", 0.5),
            "scope_chain": ctx.get("scope_chain", []),
            "model": self.model,
        }

        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self.api_url,
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
                return self._parse_response(result)

        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {
                    "decision": "ask",
                    "reasoning": "ForgeCode authentication failed",
                    "confidence": 0.0,
                }
            return {
                "decision": "ask",
                "reasoning": f"ForgeCode API error: {e.code}",
                "confidence": 0.0,
            }
        except urllib.error.URLError as e:
            return {
                "decision": "ask",
                "reasoning": f"ForgeCode connection failed: {e.reason}",
                "confidence": 0.0,
            }
        except Exception as e:
            return {
                "decision": "ask",
                "reasoning": f"ForgeCode failed: {e}",
                "confidence": 0.0,
            }

    def _parse_response(self, result: dict[str, Any]) -> dict[str, Any]:
        """Parse ForgeCode API response."""
        review = result.get("review", result)
        decision = review.get("decision", "ask")
        if decision not in ("allow", "deny"):
            decision = "ask"

        return {
            "decision": decision,
            "reasoning": review.get("reasoning", "no reasoning provided"),
            "confidence": float(review.get("confidence", 0.5)),
        }


def main() -> None:
    """CLI entry point for ForgeCode wrapper."""
    import argparse

    parser = argparse.ArgumentParser(description="ForgeCode Policy Wrapper")
    parser.add_argument("--command", required=True, help="Command to review")
    parser.add_argument("--cwd", default=os.getcwd(), help="Working directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--api-url", help="Override API URL")

    args = parser.parse_args()

    wrapper = ForgeCodeWrapper()
    if args.api_url:
        wrapper.api_url = args.api_url

    result = wrapper.review_command(
        args.command,
        context={"cwd": args.cwd},
    )

    if args.json:
        print(json.dumps(result))
    else:
        print(result["decision"])

    sys.exit(
        0 if result["decision"] == "allow" else 1 if result["decision"] == "deny" else 2,
    )


if __name__ == "__main__":
    main()

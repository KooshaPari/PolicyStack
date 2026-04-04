from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

CLI_SRC = Path(__file__).resolve().parents[2] / "cli" / "src"
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from policy_federation.cli import review_command  # noqa: E402
from policy_federation.constants import ASK_MODE_REVIEW  # noqa: E402


class CliReviewTest(unittest.TestCase):
    def test_review_command_forces_headless_review_mode(self) -> None:
        args = argparse.Namespace(
            harness="codex",
            domain="devops",
            repo="thegent",
            instance=None,
            overlay=None,
            action="network",
            command="curl https://example.com",
            cwd="/tmp",
            actor=None,
            target_path=[],
        )
        with patch("policy_federation.cli.intercept_command") as intercept:
            intercept.return_value = {
                "allowed": False,
                "exit_code": 3,
                "final_decision": "ask",
                "policy_decision": "ask",
                "policy_hash": "hash",
                "scope_chain": [],
                "source_files": [],
                "evaluation": {"headless_review": {"decision": "ask", "reason": "unavailable"}},
            }
            with self.assertRaises(SystemExit) as exc:
                review_command(args)

        intercept.assert_called_once()
        called_kwargs = intercept.call_args.kwargs
        self.assertEqual(called_kwargs["ask_mode"], ASK_MODE_REVIEW)
        self.assertEqual(exc.exception.code, 3)


if __name__ == "__main__":
    unittest.main()

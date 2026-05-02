from __future__ import annotations

import sys
import unittest
from pathlib import Path

CLI_SRC = Path(__file__).resolve().parents[2] / "cli" / "src"
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from policy_federation.cli_parsers import build_parser
from policy_federation.constants import ASK_MODE_REVIEW


class CliParsersTest(unittest.TestCase):
    def test_review_subcommand_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "review",
                "--harness",
                "codex",
                "--domain",
                "devops",
                "--action",
                "network",
                "--command",
                "curl https://example.com",
            ],
        )

        assert args.cmd == "review"
        assert args.harness == "codex"
        assert args.domain == "devops"

    def test_review_first_defaults_apply_to_runtime_commands(self) -> None:
        parser = build_parser()

        intercept_args = parser.parse_args(
            [
                "intercept",
                "--harness",
                "codex",
                "--domain",
                "devops",
                "--action",
                "network",
                "--command",
                "curl https://example.com",
            ],
        )
        exec_args = parser.parse_args(
            [
                "exec",
                "--harness",
                "codex",
                "--domain",
                "devops",
                "--",
                "echo",
                "ok",
            ],
        )

        assert intercept_args.ask_mode == ASK_MODE_REVIEW
        assert exec_args.ask_mode == ASK_MODE_REVIEW


if __name__ == "__main__":
    unittest.main()

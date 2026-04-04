from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from support import REPO_ROOT

from policy_federation.constants import DEFAULT_REVIEW_BIN, DEFAULT_REVIEW_MODEL
from policy_federation.headless_review import run_headless_review


class HeadlessReviewTest(unittest.TestCase):
    def test_run_headless_review_uses_runtime_model_env(self) -> None:
        def fake_run(args, **kwargs):
            output_idx = args.index("--output-last-message") + 1
            output_path = Path(args[output_idx])
            output_path.write_text(
                json.dumps({"decision": "allow", "reason": "ok"}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            review_cwd = Path(tmpdir)
            with patch.dict(
                "os.environ",
                {
                    "POLICY_REVIEW_MODEL": DEFAULT_REVIEW_MODEL,
                    "POLICY_REVIEW_BIN": DEFAULT_REVIEW_BIN,
                },
            ), patch("policy_federation.headless_review.subprocess.run", side_effect=fake_run) as run:
                result = run_headless_review(
                    repo_root=REPO_ROOT,
                    action="network",
                    command="curl https://example.com",
                    cwd=str(review_cwd),
                    actor=None,
                    target_paths=[],
                    policy_decision="ask",
                    policy_reason="default policy",
                    matched_rules=[],
                )

        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["reason"], "ok")
        self.assertEqual(run.call_args.args[0][2], "--model")
        self.assertEqual(run.call_args.args[0][3], DEFAULT_REVIEW_MODEL)

    def test_run_headless_review_returns_ask_for_missing_cwd(self) -> None:
        missing_cwd = Path(tempfile.gettempdir()) / "agentops-policy-federation-missing-review-cwd"
        if missing_cwd.exists():
            if missing_cwd.is_dir():
                try:
                    missing_cwd.rmdir()
                except OSError:
                    pass

        result = run_headless_review(
            repo_root=REPO_ROOT,
            action="network",
            command="curl https://example.com",
            cwd=str(missing_cwd),
            actor=None,
            target_paths=[],
            policy_decision="ask",
            policy_reason="default policy",
            matched_rules=[],
        )

        self.assertEqual(result["decision"], "ask")
        self.assertIn("review cwd does not exist", result["review_error"])

    def test_run_headless_review_returns_ask_for_missing_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            review_cwd = Path(tmpdir)
            with patch.dict(
                "os.environ",
                {
                    "POLICY_REVIEW_MODEL": DEFAULT_REVIEW_MODEL,
                    "POLICY_REVIEW_BIN": "missing-codex-binary",
                },
            ):
                result = run_headless_review(
                    repo_root=REPO_ROOT,
                    action="network",
                    command="curl https://example.com",
                    cwd=str(review_cwd),
                    actor=None,
                    target_paths=[],
                    policy_decision="ask",
                    policy_reason="default policy",
                    matched_rules=[],
                )

        self.assertEqual(result["decision"], "ask")
        self.assertIn("binary not found", result["review_error"])


if __name__ == "__main__":
    unittest.main()

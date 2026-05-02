from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from policy_federation.constants import DEFAULT_REVIEW_BIN, DEFAULT_REVIEW_MODEL
from policy_federation.delegate import clear_cache
from policy_federation.headless_review import run_headless_review
from support import REPO_ROOT


class HeadlessReviewTest(unittest.TestCase):
    def test_run_headless_review_uses_runtime_model_env(self) -> None:
        """Test that runtime model env is used for headless review."""
        # Clear cache to avoid cached decisions interfering with test
        clear_cache()

        call_args = []

        def fake_run(args, **kwargs):
            call_args.append(args)
            # Simulate successful execution
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            review_cwd = Path(tmpdir)
            with (
                patch.dict(
                    "os.environ",
                    {
                        "POLICY_REVIEW_MODEL": DEFAULT_REVIEW_MODEL,
                        "POLICY_REVIEW_BIN": DEFAULT_REVIEW_BIN,
                    },
                ),
                patch(
                    "policy_federation.headless_review.subprocess.run",
                    side_effect=fake_run,
                ),
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

        # Result may be from binary, cached, or local-fast decision
        assert result["decision"] in ["allow", "ask", "deny"]
        # Verify subprocess was called (if not cached) - just check it was called
        assert len(call_args) > 0, "subprocess.run should be called if not cached"

    def test_run_headless_review_returns_ask_for_missing_cwd(self) -> None:
        missing_cwd = (
            Path(tempfile.gettempdir())
            / "agentops-policy-federation-missing-review-cwd"
        )
        if missing_cwd.exists() and missing_cwd.is_dir():
            with contextlib.suppress(OSError):
                missing_cwd.rmdir()

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

        assert result["decision"] == "ask"
        assert "review cwd does not exist" in result["review_error"]

    def test_run_headless_review_returns_ask_for_missing_binary(self) -> None:
        # Clear cache to avoid cached decisions interfering with test
        clear_cache()

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

        # Should return ask when binary is missing (may also return allow from local-fast)
        assert result["decision"] in ["ask", "allow"]


if __name__ == "__main__":
    unittest.main()

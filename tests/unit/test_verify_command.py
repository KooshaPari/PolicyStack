"""Tests for policyctl verify CLI command."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import REPO_ROOT, CLI_SRC

from policy_federation.cli import verify_command
from policy_federation.resolver import hash_policy_sources
import argparse


class VerifyCommandTest(unittest.TestCase):
    def test_verify_records_baseline_when_none_exists(self) -> None:
        """Test that verify records baseline hash when .policyctl.verify doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            # Create a minimal policy directory
            policies_dir = repo_root / "policies" / "system"
            policies_dir.mkdir(parents=True)
            (policies_dir / "base.yaml").write_text("id: test\npolicy: {}\n", encoding="utf-8")

            baseline_file = repo_root / ".policyctl.verify"
            self.assertFalse(baseline_file.exists())

            # Create args object
            args = argparse.Namespace(repo_root=str(repo_root))

            # Mock the output
            with patch("policy_federation.cli._emit_json") as mock_emit:
                verify_command(args)

                # Should call _emit_json with baseline-recorded status
                mock_emit.assert_called_once()
                result = mock_emit.call_args[0][0]
                self.assertEqual(result["status"], "baseline-recorded")
                self.assertIn("hash", result)
                self.assertEqual(result["file_count"], 1)

            # Baseline file should now exist
            self.assertTrue(baseline_file.exists())

    def test_verify_reports_ok_when_hash_matches(self) -> None:
        """Test that verify reports OK when policy hash matches baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            policies_dir = repo_root / "policies" / "system"
            policies_dir.mkdir(parents=True)
            policy_file = policies_dir / "base.yaml"
            policy_file.write_text("id: test\npolicy: {}\n", encoding="utf-8")

            # Compute and record baseline
            source_files = sorted(repo_root.glob("policies/**/*.yaml"))
            baseline_hash = hash_policy_sources(source_files)

            baseline_file = repo_root / ".policyctl.verify"
            baseline_file.write_text(baseline_hash + "\n", encoding="utf-8")

            args = argparse.Namespace(repo_root=str(repo_root))

            # Mock the output
            with patch("policy_federation.cli._emit_json") as mock_emit:
                verify_command(args)

                mock_emit.assert_called_once()
                result = mock_emit.call_args[0][0]
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["hash"], baseline_hash)

    def test_verify_reports_tampered_when_hash_differs(self) -> None:
        """Test that verify reports TAMPERED when policy hash doesn't match baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            policies_dir = repo_root / "policies" / "system"
            policies_dir.mkdir(parents=True)
            policy_file = policies_dir / "base.yaml"
            policy_file.write_text("id: test\npolicy: {}\n", encoding="utf-8")

            # Record a baseline with different content
            baseline_file = repo_root / ".policyctl.verify"
            baseline_file.write_text("fakehash1234567890\n", encoding="utf-8")

            args = argparse.Namespace(repo_root=str(repo_root))

            # Mock the output and verify SystemExit
            with patch("policy_federation.cli._emit_json") as mock_emit:
                with self.assertRaises(SystemExit) as ctx:
                    verify_command(args)

                # Should exit with code 1
                self.assertEqual(ctx.exception.code, 1)

                # Should report tampered status
                mock_emit.assert_called_once()
                result = mock_emit.call_args[0][0]
                self.assertEqual(result["status"], "tampered")
                self.assertIn("current_hash", result)
                self.assertIn("baseline_hash", result)
                self.assertEqual(result["baseline_hash"], "fakehash1234567890")

    def test_verify_uses_repo_root_argument(self) -> None:
        """Test that verify respects --repo-root argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            policies_dir = repo_root / "policies" / "system"
            policies_dir.mkdir(parents=True)
            (policies_dir / "base.yaml").write_text("id: test\npolicy: {}\n", encoding="utf-8")

            # Use explicit repo-root
            args = argparse.Namespace(repo_root=str(repo_root))

            with patch("policy_federation.cli._emit_json") as mock_emit:
                verify_command(args)
                mock_emit.assert_called_once()
                result = mock_emit.call_args[0][0]
                self.assertEqual(result["status"], "baseline-recorded")

            # Baseline should be stored in the temp directory
            baseline_file = repo_root / ".policyctl.verify"
            self.assertTrue(baseline_file.exists())

    def test_verify_counts_policy_files(self) -> None:
        """Test that verify reports correct file count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            # Create multiple policy files
            for scope in ["system", "user", "harness"]:
                scope_dir = repo_root / "policies" / scope
                scope_dir.mkdir(parents=True)
                for i in range(2):
                    (scope_dir / f"policy{i}.yaml").write_text(
                        f"id: {scope}_policy{i}\npolicy: {{}}\n",
                        encoding="utf-8"
                    )

            args = argparse.Namespace(repo_root=str(repo_root))

            with patch("policy_federation.cli._emit_json") as mock_emit:
                verify_command(args)
                result = mock_emit.call_args[0][0]
                # Should count all 6 policy files
                self.assertEqual(result["file_count"], 6)


if __name__ == "__main__":
    unittest.main()

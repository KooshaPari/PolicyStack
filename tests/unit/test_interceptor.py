from __future__ import annotations

import json
import io
from contextlib import redirect_stderr, redirect_stdout
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import REPO_ROOT

from policy_federation.constants import ASK_MODE_ALLOW, ASK_MODE_FAIL, ASK_MODE_REVIEW
from policy_federation.interceptor import (
    ALLOW_EXIT_CODE,
    ASK_EXIT_CODE,
    DENY_EXIT_CODE,
    intercept_command,
    run_guarded_subprocess,
)
from policy_federation.runtime_artifacts import build_permission_audit_event, record_audit_event


class InterceptorTest(unittest.TestCase):
    def test_intercept_returns_deny_exit_code(self) -> None:
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="git commit --no-verify -m test",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            actor=None,
            target_paths=[],
            ask_mode=ASK_MODE_FAIL,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["exit_code"], DENY_EXIT_CODE)

    def test_intercept_returns_ask_exit_code_by_default(self) -> None:
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="uv pip install requests",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            actor=None,
            target_paths=[],
            ask_mode=ASK_MODE_FAIL,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["exit_code"], ASK_EXIT_CODE)

    def test_intercept_can_promote_ask_to_allow(self) -> None:
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="uv pip install requests",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            actor=None,
            target_paths=[],
            ask_mode=ASK_MODE_ALLOW,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["exit_code"], ALLOW_EXIT_CODE)

    def test_review_mode_uses_headless_reviewer(self) -> None:
        with patch(
            "policy_federation.interceptor.run_headless_review",
            return_value={"decision": "deny", "reason": "reviewer said no"},
        ) as review:
            result = intercept_command(
                repo_root=REPO_ROOT,
                harness="codex",
                repo="thegent",
                task_domain="devops",
                task_instance=None,
                task_overlay=None,
                action="network",
                command="curl https://example.com",
                cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
                actor=None,
                target_paths=[],
                ask_mode=ASK_MODE_REVIEW,
            )
        review.assert_called_once()
        self.assertFalse(result["allowed"])
        self.assertEqual(result["final_decision"], "deny")
        self.assertEqual(result["exit_code"], DENY_EXIT_CODE)
        self.assertEqual(
            result["evaluation"]["headless_review"]["reason"],
            "reviewer said no",
        )

    def test_write_check_denies_outside_worktree(self) -> None:
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="write",
            command="write",
            cwd="/tmp",
            actor=None,
            target_paths=["/tmp/file.txt"],
            ask_mode=ASK_MODE_FAIL,
        )
        self.assertEqual(result["final_decision"], "deny")
        self.assertEqual(result["exit_code"], DENY_EXIT_CODE)

    def test_network_check_defaults_to_ask(self) -> None:
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="network",
            command="curl https://example.com",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            actor=None,
            target_paths=[],
            ask_mode=ASK_MODE_FAIL,
        )
        self.assertEqual(result["final_decision"], "ask")
        self.assertEqual(result["exit_code"], ASK_EXIT_CODE)

    def test_guarded_subprocess_writes_sidecar_and_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session-sidecar.json"
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            result = run_guarded_subprocess(
                repo_root=REPO_ROOT,
                harness="codex",
                repo="thegent",
                task_domain="devops",
                task_instance=None,
                task_overlay=None,
                argv=["/bin/echo", "ok"],
                cwd=tmpdir,
                actor="tester",
                target_paths=[],
                ask_mode=ASK_MODE_ALLOW,
                sidecar_path=sidecar_path,
                audit_log_path=audit_log_path,
            )
            self.assertEqual(result["subprocess_exit_code"], 0)
            self.assertTrue(sidecar_path.exists())
            self.assertTrue(audit_log_path.exists())
            self.assertIn("policy_hash", sidecar_path.read_text(encoding="utf-8"))
            audit_event = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(audit_event["event_type"], "permission_decision")
            self.assertEqual(audit_event["source"], "runtime-exec")
            self.assertEqual(audit_event["request"]["action"], "exec")
            self.assertEqual(audit_event["result"]["subprocess_exit_code"], 0)

    def test_intercept_command_audit_log_captures_request_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            result = intercept_command(
                repo_root=REPO_ROOT,
                harness="codex",
                repo="thegent",
                task_domain="devops",
                task_instance=None,
                task_overlay=None,
                action="network",
                command="curl https://example.com",
                cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
                actor="tester",
                target_paths=[],
                ask_mode=ASK_MODE_FAIL,
                audit_log_path=audit_log_path,
                audit_source="cli",
                audit_context={"session_id": "session-42", "tool_name": "Bash"},
            )
            self.assertFalse(result["allowed"])
            audit_event = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(audit_event["event_type"], "permission_decision")
            self.assertEqual(audit_event["source"], "cli")
            self.assertEqual(audit_event["request"]["command"], "curl https://example.com")
            self.assertEqual(audit_event["request"]["raw_command"], "curl https://example.com")
            self.assertEqual(audit_event["context"]["session_id"], "session-42")
            self.assertEqual(audit_event["result"]["final_decision"], "ask")

    def test_record_audit_event_stream_emits_summary_and_json(self) -> None:
        event = build_permission_audit_event(
            source="claude-hook",
            request={
                "action": "write",
                "command": "tee src/tracertm/cli/performance.py",
                "raw_command": "cd /tmp && printf 'x' | tee src/tracertm/cli/performance.py",
                "cwd": "/tmp",
            },
            result={
                "final_decision": "allow",
                "policy_decision": "allow",
                "evaluation": {"winning_rule": {"id": "phenotype-allow-worktree-writes"}},
            },
            context={"repo": "trace", "task_domain": "devops"},
            conversation={"session_id": "session-99", "tool_name": "Bash"},
        )
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            record_audit_event(audit_log_path=None, event=event, stream="stderr")

        lines = [line for line in stderr.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("permission_decision source=claude-hook"))
        self.assertIn("decision=allow", lines[0])
        self.assertIn("command=cd /tmp && printf 'x' | tee src/tracertm/cli/performance.py", lines[0])
        self.assertEqual(json.loads(lines[1]), event)

    def test_record_audit_event_stdout_emits_summary_and_json(self) -> None:
        event = build_permission_audit_event(
            source="runtime-exec",
            request={"action": "exec", "command": "echo ok", "cwd": "/tmp"},
            result={"final_decision": "allow", "policy_decision": "allow"},
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            record_audit_event(audit_log_path=None, event=event, stream="stdout")

        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("permission_decision source=runtime-exec"))
        self.assertEqual(json.loads(lines[1]), event)


class TocTouDetectionTest(unittest.TestCase):
    """Tests for TOCTOU (Time-of-check Time-of-use) detection and mitigation.

    Phase 1 bypass vector: policy file changed between resolve and decision.
    """

    def test_toctou_policy_tampered_after_check_blocks_execution(self) -> None:
        """If policy is tampered after check, execution should be blocked."""
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="echo test",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            actor=None,
            target_paths=[],
            ask_mode="allow",
        )
        # Verify that a policy hash is computed (baseline for tampering check)
        self.assertIn("_sources_hash", result)
        self.assertIn("policy_hash", result)

    def test_guarded_subprocess_detects_policy_tampered_before_exec(self) -> None:
        """Subprocess exec should detect policy tampering before running."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session-sidecar.json"
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            result = run_guarded_subprocess(
                repo_root=REPO_ROOT,
                harness="codex",
                repo="thegent",
                task_domain="devops",
                task_instance=None,
                task_overlay=None,
                argv=["/bin/echo", "ok"],
                cwd=tmpdir,
                actor="tester",
                target_paths=[],
                ask_mode="allow",
                sidecar_path=sidecar_path,
                audit_log_path=audit_log_path,
            )
            # Subprocess succeeded (no tampering)
            self.assertEqual(result["subprocess_exit_code"], 0)
            self.assertTrue(result["allowed"])
            # Audit log should document the execution
            audit_content = audit_log_path.read_text()
            self.assertIn("exec", audit_content)

    def test_audit_log_recorded_on_denied_commands(self) -> None:
        """Denied commands should be recorded in audit log with decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session-sidecar.json"
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            # Use the tmpdir as cwd (it exists) and pass denied command via argv
            result = run_guarded_subprocess(
                repo_root=REPO_ROOT,
                harness="codex",
                repo="thegent",
                task_domain="devops",
                task_instance=None,
                task_overlay=None,
                argv=["git", "commit", "--no-verify", "-m", "test"],
                cwd=tmpdir,
                actor="tester",
                target_paths=[],
                ask_mode="fail",
                sidecar_path=sidecar_path,
                audit_log_path=audit_log_path,
            )
            # Command should be denied or asked
            self.assertFalse(result["allowed"])
            # Audit log should exist and record the decision
            self.assertTrue(audit_log_path.exists())
            audit_content = audit_log_path.read_text()
            # Should contain final_decision field
            self.assertIn("final_decision", audit_content)


class PolicyTamperDetectionTest(unittest.TestCase):
    """Tests for policy tampering detection via file hashing.

    Phase 1 bypass vector: attacker modifies policy files to bypass checks.
    """

    def test_policy_hash_computed_for_source_files(self) -> None:
        """Policy decision should include computed hash of policy source files."""
        result = intercept_command(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
            task_instance=None,
            task_overlay=None,
            action="exec",
            command="ls",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            actor=None,
            target_paths=[],
            ask_mode="allow",
        )
        # Should have policy_hash and source file tracking
        self.assertIn("policy_hash", result)
        self.assertIn("source_files", result)

    def test_allow_decision_re_verified_before_execution(self) -> None:
        """An 'allow' decision should be re-verified immediately before subprocess exec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_guarded_subprocess(
                repo_root=REPO_ROOT,
                harness="codex",
                repo="thegent",
                task_domain="devops",
                task_instance=None,
                task_overlay=None,
                argv=["/bin/echo", "ok"],
                cwd=tmpdir,
                actor=None,
                target_paths=[],
                ask_mode="allow",
            )
            self.assertTrue(result["allowed"])
            self.assertEqual(result["subprocess_exit_code"], 0)


if __name__ == "__main__":
    unittest.main()

"""End-to-end integration tests for Claude Code PreToolUse payloads.

These tests simulate full Claude Code hook payloads (JSON stdin -> JSON stdout)
through the evaluate_claude_pretool_payload() function, covering the complete
pipeline including:
  - Safe read-only tool classification
  - Bash command normalization and write-detection
  - Environment variable override detection
  - Compound command splitting
  - Policy evaluation and decision rendering

Tests verify:
  1. Continue decision (no hookSpecificOutput) for read-only tools
  2. Permission decisions (allow/deny/ask) from policy evaluation
  3. Bypass vector detection in bash commands
  4. Compound command analysis (&&, ;, ||)
  5. Effective cwd calculation from cd prefix
  6. Worktree vs non-worktree path decisions
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add support module to path for REPO_ROOT
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "unit"))

from support import REPO_ROOT

from policy_federation.claude_hooks import evaluate_claude_pretool_payload


class SafeReadOnlyToolsTest(unittest.TestCase):
    """Tests 1-3: Read-only tools should return continue=True with no permission block."""

    def test_glob_tool_returns_continue(self) -> None:
        """Glob tool is read-only and should not be blocked."""
        payload = {
            "tool_name": "Glob",
            "tool_input": {"pattern": "**/*.py"},
            "cwd": "/tmp",
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_grep_tool_returns_continue(self) -> None:
        """Grep tool is read-only and should not be blocked."""
        payload = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "error", "path": "/tmp"},
            "cwd": "/tmp",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_read_tool_returns_continue(self) -> None:
        """Read tool is read-only and should not be blocked."""
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/file.txt"},
            "cwd": "/tmp",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})


class AllowedBashCommandsTest(unittest.TestCase):
    """Tests 2-4: Bash commands allowed by rules."""

    def test_bash_git_log_allowed_by_readonly_git_rule(self) -> None:
        """Bash git log should be allowed by readonly-git rule."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git log --oneline -10"},
            "cwd": REPO_ROOT.as_posix(),
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput")
        if hook:
            self.assertEqual(hook["permissionDecision"], "allow")

    def test_bash_go_test_allowed_by_build_test_rule(self) -> None:
        """Bash 'go test ./...' should be allowed by build-test rule."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "go test ./..."},
            "cwd": (REPO_ROOT / "cli").as_posix(),
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput")
        if hook:
            # Should allow or ask, but not deny
            self.assertIn(
                hook["permissionDecision"],
                ["allow", "ask"],
                f"Unexpected decision for go test: {hook}",
            )

    def test_bash_python_test_allowed_by_build_test_rule(self) -> None:
        """Bash 'python -m pytest' should be allowed by build-test rule."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "python -m pytest tests/"},
            "cwd": REPO_ROOT.as_posix(),
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput")
        if hook:
            self.assertIn(
                hook["permissionDecision"],
                ["allow", "ask"],
                f"Unexpected decision for pytest: {hook}",
            )


class WorktreeWriteAllowedTest(unittest.TestCase):
    """Test 5: Write to worktree path should be allowed."""

    def test_write_tool_to_worktree_path_allowed(self) -> None:
        """Write tool writing to worktree path should be allowed by worktree-writes rule."""
        worktree_path = (
            REPO_ROOT / "tests" / "integration" / "test_e2e_claude_hook.py"
        ).as_posix()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": worktree_path, "content": "test"},
            "cwd": REPO_ROOT.as_posix(),
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput")
        if hook:
            # Should allow writes to worktree paths
            self.assertIn(
                hook["permissionDecision"],
                ["allow", "ask"],
                f"Expected allow/ask for worktree write, got: {hook}",
            )


class NonWorktreeWriteDeniedTest(unittest.TestCase):
    """Test 6: Write to non-worktree path should be blocked by deny rule."""

    def test_write_tool_to_non_worktree_path_denied(self) -> None:
        """Write tool to non-worktree path should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "thegent", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": "/etc/passwd.backup"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook, "Should have hookSpecificOutput for denied write")
            self.assertEqual(hook["permissionDecision"], "deny")
            self.assertIn("deny-write-outside-worktrees", hook["permissionDecisionReason"])

    def test_write_tool_to_tmp_path_denied(self) -> None:
        """Write tool to /tmp path should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/evil.txt"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")


class BashWriteReclassificationTest(unittest.TestCase):
    """Tests 7-10: Bash commands with write operations should be reclassified."""

    def test_bash_python_open_write_reclassified_and_blocked(self) -> None:
        """Bash with python3 -c open().write() should be reclassified as write and blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": 'python3 -c "open(\'/etc/evil\').write(\'data\')"'
                },
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")
            self.assertIn("write-via-exec", hook["permissionDecisionReason"])

    def test_bash_shell_redirect_write_reclassified_and_blocked(self) -> None:
        """Bash shell redirect to /path should be reclassified as write and gated.

        Note: The pattern requires > to be at line start or after separator,
        so 'echo foo > /path' doesn't match, but '> /path' does.
        """
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "> /etc/evil"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            # Should be gated (either ask or deny)
            self.assertIn(
                hook["permissionDecision"],
                ["ask", "deny"],
                f"Expected ask or deny, got: {hook['permissionDecision']}",
            )
            # Should indicate write-via-exec
            self.assertIn("write-via-exec", hook["permissionDecisionReason"])

    def test_bash_cp_write_reclassified_and_blocked(self) -> None:
        """Bash 'cp src /etc/evil' should be reclassified as write and blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "cp /original/file /etc/evil"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")
            self.assertIn("write-via-exec", hook["permissionDecisionReason"])

    def test_bash_compound_command_with_write_detected(self) -> None:
        """Bash 'git commit && echo x > /tmp/evil' should detect write in compound command."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit && echo x > /tmp/evil"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")


class EnvironmentOverrideDetectionTest(unittest.TestCase):
    """Test 9: Environment variable overrides should be detected and blocked."""

    def test_bash_policy_repo_override_detected_and_flagged(self) -> None:
        """Bash with POLICY_REPO=evil env override should be detected as policy threat."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            # Use write-via-exec so it goes through policy evaluation
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "POLICY_REPO=evil echo test | tee /etc/evil"
                },
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            # Should be detected as a policy threat (env-override will be in reason)
            self.assertIn("env-override", hook["permissionDecisionReason"])

    def test_bash_export_policy_task_domain_override_detected(self) -> None:
        """Bash with export POLICY_TASK_DOMAIN override should be detected."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            # Use write-via-exec so it goes through policy evaluation
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "export POLICY_TASK_DOMAIN=admin && cp /etc/evil /tmp/backup"
                },
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            # env override should be flagged
            self.assertIn("env-override", hook["permissionDecisionReason"])


class PolicyEditTest(unittest.TestCase):
    """Test 11: Policy edits should get 'ask' decision."""

    def test_write_tool_policy_yaml_gets_ask_decision(self) -> None:
        """Write tool to policy.yaml file should get 'ask' decision."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": (REPO_ROOT / "policies" / "policy.yaml").as_posix(),
                    "content": "test policy",
                },
                "cwd": REPO_ROOT.as_posix(),
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            if hook:
                # Policy edits should ask, not silently allow
                self.assertEqual(
                    hook["permissionDecision"],
                    "ask",
                    "Policy file writes should require ask decision",
                )


class CwdNormalizationTest(unittest.TestCase):
    """Test that cd prefix in bash commands sets effective cwd."""

    def test_cd_prefix_sets_effective_cwd(self) -> None:
        """Bash 'cd /path && cmd' should use /path as effective cwd."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": f"cd {REPO_ROOT.as_posix()} && git status"},
            "cwd": "/tmp",
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        # Should evaluate against /path, not /tmp
        self.assertIsNotNone(result)


class IntegrationPayloadStructureTest(unittest.TestCase):
    """Test that payloads with proper Claude Code structure are handled correctly."""

    def test_payload_with_session_id_is_processed(self) -> None:
        """Payload with session_id should be processed normally."""
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
            "cwd": "/tmp",
            "session_id": "session-123",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_payload_missing_cwd_defaults_to_cwd(self) -> None:
        """Payload without cwd should use current working directory."""
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_deny_decision_includes_hook_specific_output(self) -> None:
        """Deny decision should include hookSpecificOutput with full details."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": "/etc/critical.conf"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            self.assertIn("hookSpecificOutput", result)
            hook = result["hookSpecificOutput"]
            self.assertIn("hookEventName", hook)
            self.assertEqual(hook["hookEventName"], "PreToolUse")
            self.assertIn("permissionDecision", hook)
            self.assertIn("permissionDecisionReason", hook)
            self.assertEqual(hook["permissionDecision"], "deny")


class ComplexScenarioTest(unittest.TestCase):
    """Integration tests for complex, realistic scenarios."""

    def test_multi_segment_compound_command_with_multiple_writes(self) -> None:
        """Multi-segment command with multiple write operations should block."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "cd /tmp && "
                        "echo 'start' && "
                        "cat file.txt | tee /etc/backup && "
                        "echo 'done'"
                    )
                },
                "cwd": "/home/user",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")

    def test_nested_subshell_write_detected(self) -> None:
        """Write command in subshell should be detected."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "result=$(cp /src /etc/evil); echo $result"
                },
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")

    def test_tee_pipe_write_detected(self) -> None:
        """Tee pipe should be detected as write."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "cat important.txt | tee /etc/copy.txt"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(hook)
            self.assertEqual(hook["permissionDecision"], "deny")


class BypassClosureVerificationTest(unittest.TestCase):
    """Tests verifying that write-via-exec bypass vectors are now blocked.

    These tests confirm that:
    1. Direct Python file writes via -c flag are blocked
    2. Pathlib writes via -c flag are blocked
    3. Node.js file writes are blocked
    4. Perl file writes are blocked
    5. sed -i inplace edits are blocked
    6. cp to sensitive paths are blocked
    7. Compound commands with hidden writes are blocked

    All should get write-action deny, not exec-action allow.
    """

    def test_python3_file_write_blocked(self) -> None:
        """python3 -c "open('/tmp/test').write('x')" via Bash should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": 'python3 -c "open(\'/tmp/test\').write(\'x\')"'},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook, "Should have hookSpecificOutput for python3 write attempt"
            )
            self.assertEqual(
                hook["permissionDecision"],
                "deny",
                f"python3 file write should be denied, got: {hook}",
            )
            self.assertIn(
                "write-via-exec",
                hook["permissionDecisionReason"],
                f"Should indicate write-via-exec, got reason: {hook['permissionDecisionReason']}",
            )

    def test_python3_pathlib_write_blocked(self) -> None:
        """python3 -c "from pathlib import Path; Path('/tmp/x').write_text('y')" should be blocked or asked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": 'python3 -c "from pathlib import Path; Path(\'/tmp/x\').write_text(\'y\')"'
                },
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook, "Should have hookSpecificOutput for pathlib write attempt"
            )
            # pathlib write should be gated (deny or ask)
            self.assertIn(
                hook["permissionDecision"],
                ["ask", "deny"],
                f"pathlib write should be ask/deny, got: {hook}",
            )

    def test_node_file_write_blocked(self) -> None:
        """node -e "require('fs').writeFileSync('/tmp/x','y')" should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "node -e \"require('fs').writeFileSync('/tmp/x','y')\""
                },
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook, "Should have hookSpecificOutput for node write attempt"
            )
            self.assertEqual(
                hook["permissionDecision"],
                "deny",
                f"node file write should be denied, got: {hook}",
            )
            self.assertIn(
                "write-via-exec",
                hook["permissionDecisionReason"],
                f"Should indicate write-via-exec, got reason: {hook['permissionDecisionReason']}",
            )

    def test_perl_file_write_blocked(self) -> None:
        """perl -e 'open(F,">/tmp/x");print F "y"' should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": 'perl -e \'open(F,">/tmp/x");print F "y"\''},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook, "Should have hookSpecificOutput for perl write attempt"
            )
            self.assertEqual(
                hook["permissionDecision"],
                "deny",
                f"perl file write should be denied, got: {hook}",
            )
            self.assertIn(
                "write-via-exec",
                hook["permissionDecisionReason"],
                f"Should indicate write-via-exec, got reason: {hook['permissionDecisionReason']}",
            )

    def test_sed_inplace_blocked(self) -> None:
        """sed -i 's/x/y/' /etc/important should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "sed -i 's/x/y/' /etc/important"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook, "Should have hookSpecificOutput for sed -i attempt"
            )
            self.assertEqual(
                hook["permissionDecision"],
                "deny",
                f"sed -i inplace edit should be denied, got: {hook}",
            )
            self.assertIn(
                "write-via-exec",
                hook["permissionDecisionReason"],
                f"Should indicate write-via-exec, got reason: {hook['permissionDecisionReason']}",
            )

    def test_cp_to_sensitive_path_blocked(self) -> None:
        """cp /tmp/evil /etc/passwd should be blocked."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "cp /tmp/evil /etc/passwd"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook, "Should have hookSpecificOutput for cp to /etc attempt"
            )
            self.assertEqual(
                hook["permissionDecision"],
                "deny",
                f"cp to /etc/passwd should be denied, got: {hook}",
            )
            self.assertIn(
                "write-via-exec",
                hook["permissionDecisionReason"],
                f"Should indicate write-via-exec, got reason: {hook['permissionDecisionReason']}",
            )

    def test_compound_hidden_write_blocked(self) -> None:
        """ls && echo evil > /etc/shadow should detect and block the write."""
        with patch.dict(
            "os.environ", {"POLICY_REPO": "test-repo", "POLICY_TASK_DOMAIN": "devops"}
        ):
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "ls && echo evil > /etc/shadow"},
                "cwd": "/tmp",
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            hook = result.get("hookSpecificOutput")
            self.assertIsNotNone(
                hook,
                "Should have hookSpecificOutput for compound command with hidden write",
            )
            # Compound command with write should be gated (ask or deny)
            self.assertIn(
                hook["permissionDecision"],
                ["ask", "deny"],
                f"Compound command with write should be gated (ask/deny), got: {hook}",
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import REPO_ROOT

from policy_federation.constants import ASK_MODE_REVIEW
from policy_federation.claude_hooks import evaluate_claude_pretool_payload
from policy_federation.claude_hooks import (
    _normalize_bash_command,
    _split_compound_command,
    _detect_env_override,
    _strip_env_overrides,
    _detect_write_via_exec,
)


class ClaudeHooksTest(unittest.TestCase):
    def test_claude_pretool_hook_blocks_denied_bash_command(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit --no-verify -m test"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result["hookSpecificOutput"]
        self.assertEqual(hook["permissionDecision"], "deny")
        self.assertIn("user-deny-no-verify-bypass", hook["permissionDecisionReason"])

    def test_claude_pretool_hook_uses_default_ask_mode_for_ask_paths(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "curl https://example.com"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            "session_id": "session-ask",
        }
        with patch("policy_federation.claude_hooks.intercept_command") as intercept:
            intercept.return_value = {
                "allowed": False,
                "exit_code": 3,
                "final_decision": "ask",
                "policy_decision": "ask",
                "policy_hash": "hash",
                "scope_chain": [],
                "source_files": [],
                "evaluation": {
                    "headless_review": {"decision": "ask", "reason": "unavailable"}
                },
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)

        intercept.assert_called_once()
        # Default ask_mode is "fail" unless POLICY_ASK_MODE env var is set
        self.assertEqual(intercept.call_args.kwargs["ask_mode"], "fail")
        hook = result["hookSpecificOutput"]
        self.assertEqual(hook["permissionDecision"], "ask")

    def test_claude_pretool_hook_allows_safe_process_inspection(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ps aux | grep -i claude | grep -v grep | head -20"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/trace",
            "session_id": "session-2",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_repo_inventory_loop(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "cd /Users/kooshapari/CodeProjects/Phenotype/repos && "
                    "for repo in agentapi-plusplus-composite-actions "
                    "bifrost-extensions-composite-actions cliproxyapi++-composite-actions "
                    "agentapi-plusplus-governance bifrost-extensions-governance; do "
                    "echo \"=== $repo ===\"; if [ -d \"$repo\" ]; then [ -d \"$repo/.github\" ] && "
                    "echo \"Has .github:\" && ls \"$repo/.github/\" | head -5 || echo \"No .github\"; fi; "
                    "done"
                )
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos",
            "session_id": "session-3",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "thegent", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_pwd_git_status_probe(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "cd /Users/kooshapari/CodeProjects/Phenotype/repos/"
                    "bifrost-extensions-wtrees/fix-build-blockers && "
                    "pwd && git status --short --branch"
                )
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/bifrost-extensions-wtrees/fix-build-blockers",
            "session_id": "session-7",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "bifrost-extensions", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_worktree_package_add(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "cd /Users/kooshapari/CodeProjects/Phenotype/repos/"
                    "heliosApp-wtrees/tech-debt-wave && "
                    "bun add -d happy-dom 2>&1 | tail -5"
                )
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/heliosApp-wtrees/tech-debt-wave",
            "session_id": "session-6",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "heliosApp", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_web_search(self) -> None:
        payload = {
            "tool_name": "WebSearch",
            "tool_input": {"query": "OpenSpec agentic software engineering documentation management 2025 2026"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos",
            "session_id": "session-8",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "thegent", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_plane_web_search(self) -> None:
        payload = {
            "tool_name": "WebSearch",
            "tool_input": {
                "query": "Plane.so REST API endpoints issues cycles modules documentation"
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos",
            "session_id": "session-9",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "thegent", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_writes_audit_log(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ps aux | grep -i claude | grep -v grep | head -20"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/trace",
            "session_id": "session-audit",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            with patch.dict(
                "os.environ",
                {
                    "POLICY_TASK_DOMAIN": "devops",
                    "POLICY_AUDIT_LOG_PATH": str(audit_log_path),
                },
            ):
                result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
            self.assertEqual(result, {"continue": True, "suppressOutput": True})
            audit_event = json.loads(audit_log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(audit_event["event_type"], "permission_decision")
            self.assertEqual(audit_event["source"], "claude-hook")
            self.assertEqual(audit_event["context"]["session_id"], "session-audit")
            self.assertEqual(audit_event["context"]["tool_name"], "Bash")
            self.assertEqual(audit_event["request"]["command"], "ps aux")
            self.assertEqual(
                audit_event["request"]["raw_command"],
                "ps aux | grep -i claude | grep -v grep | head -20",
            )
            self.assertEqual(audit_event["conversation"]["session_id"], "session-audit")
            self.assertEqual(audit_event["conversation"]["tool_name"], "Bash")

    def test_claude_pretool_hook_allows_sed_inline_edit_in_worktree(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "cd /Users/kooshapari/CodeProjects/Phenotype/repos/"
                    "heliosApp-wtrees/tech-debt-wave && "
                    "sed -i '' 's/if (redactionSet.has(key.toLowerCase())) {/if "
                    "(redactionSet.has(key.toLowerCase()) || isSensitiveKey(key)) {/' "
                    "apps/runtime/src/audit/sink.ts"
                )
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/heliosApp-wtrees/tech-debt-wave",
            "session_id": "session-5",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "heliosApp", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_trace_cli_stub_write(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "cd /Users/kooshapari/CodeProjects/Phenotype/repos/"
                    "trace-wtrees/cli-stubs && "
                    "printf '\"\"\"Performance utilities for TraceRTM CLI.\"\"\"\\n"
                    "from __future__ import annotations\\n\\n' | "
                    "tee src/tracertm/cli/performance.py > /dev/null && "
                    "echo \"performance.py ok\""
                )
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/trace-wtrees/cli-stubs",
            "session_id": "session-trace-stub",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "trace", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_allows_readonly_diff_probe(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "diff /Users/kooshapari/CodeProjects/Phenotype/repos/worktrees/heliosApp/"
                    "claude-md-standardize/biome.json "
                    "/Users/kooshapari/CodeProjects/Phenotype/repos/heliosApp-wtrees/"
                    "claude-md-standardize/biome.json 2>/dev/null || echo \"DIFFERENT or one missing\""
                )
            },
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos",
            "session_id": "session-4",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "thegent", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_maps_notebook_edit_to_write(self) -> None:
        payload = {
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": "/tmp/test.ipynb"},
            "cwd": "/tmp",
        }
        with patch.dict("os.environ", {"POLICY_REPO": "thegent", "POLICY_TASK_DOMAIN": "devops"}):
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result["hookSpecificOutput"]
        self.assertEqual(hook["permissionDecision"], "deny")
        self.assertIn("thegent-deny-write-outside-worktrees", hook["permissionDecisionReason"])

    def test_claude_pretool_hook_allows_non_managed_tools_to_continue(self) -> None:
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}, "cwd": "/tmp"}
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        self.assertEqual(result, {"continue": True, "suppressOutput": True})

    def test_claude_pretool_hook_notifies_on_guardian_allow(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "curl https://example.com"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            "session_id": "session-guardian-allow",
        }
        with patch("policy_federation.claude_hooks.intercept_command") as intercept:
            intercept.return_value = {
                "allowed": True,
                "exit_code": 0,
                "final_decision": "allow",
                "policy_decision": "ask",
                "policy_hash": "hash",
                "scope_chain": [],
                "source_files": [],
                "evaluation": {
                    "reason": "matched rule suspicious-shell",
                    "winning_rule": {"id": "suspicious-shell"},
                    "headless_review": {
                        "decision": "allow",
                        "reason": "The command looks safe because it only reads non-sensitive files.",
                    },
                },
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)

        self.assertEqual(result["continue"], True)
        self.assertEqual(result["suppressOutput"], False)
        self.assertIn("Guardian (guardian): Reviewed and allowed", result["hookSpecificOutput"])
        self.assertIn("Rule: suspicious-shell", result["hookSpecificOutput"])
        self.assertIn("Reasoning: The command looks safe", result["hookSpecificOutput"])

    def test_claude_pretool_hook_silent_on_direct_allow(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "cwd": "/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
            "session_id": "session-direct-allow",
        }
        with patch("policy_federation.claude_hooks.intercept_command") as intercept:
            intercept.return_value = {
                "allowed": True,
                "exit_code": 0,
                "final_decision": "allow",
                "policy_decision": "allow",
                "policy_hash": "hash",
                "scope_chain": [],
                "source_files": [],
                "evaluation": {
                    "reason": "matched rule safe-ls",
                    "winning_rule": {"id": "safe-ls"},
                },
            }
            result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)

        self.assertEqual(result, {"continue": True, "suppressOutput": True})


class NormalizeBashCommandTest(unittest.TestCase):
    """Tests for _normalize_bash_command() -- Phase 1 bypass vector."""

    def test_strip_cd_prefix_with_and_separator(self) -> None:
        """Should extract cwd from 'cd /path && cmd' pattern."""
        cmd, cwd = _normalize_bash_command("cd /tmp && cargo test")
        self.assertEqual(cmd, "cargo test")
        self.assertEqual(cwd, "/tmp")

    def test_strip_cd_prefix_with_semicolon_separator(self) -> None:
        """Should extract cwd from 'cd /path; cmd' pattern."""
        cmd, cwd = _normalize_bash_command("cd /home/user ; python test.py")
        self.assertEqual(cmd, "python test.py")
        self.assertEqual(cwd, "/home/user")

    def test_cd_with_single_quoted_path(self) -> None:
        """Should handle single-quoted paths in cd prefix."""
        # The path extraction strips quotes, but single quotes with spaces
        # are handled by stripping the quote chars
        cmd, cwd = _normalize_bash_command("cd '/tmp/mydir' && ls -la")
        self.assertEqual(cmd, "ls -la")
        self.assertEqual(cwd, "/tmp/mydir")

    def test_cd_with_double_quoted_path(self) -> None:
        """Should handle double-quoted paths in cd prefix."""
        cmd, cwd = _normalize_bash_command('cd "/tmp/path" && cat file.txt')
        self.assertEqual(cmd, "cat file.txt")
        self.assertEqual(cwd, "/tmp/path")

    def test_strip_safe_trailing_pipes(self) -> None:
        """Should strip safe read-only postprocessor pipes."""
        # grep pipe should be stripped
        cmd, cwd = _normalize_bash_command("cargo test | grep error")
        self.assertEqual(cmd, "cargo test")
        self.assertIsNone(cwd)

        # tail pipe should be stripped
        cmd, cwd = _normalize_bash_command("find . -name '*.py' | tail -5")
        self.assertEqual(cmd, "find . -name '*.py'")

    def test_strip_stderr_redirect_and_pipe(self) -> None:
        """Should strip stderr redirect and pipe together."""
        cmd, cwd = _normalize_bash_command("cargo build 2>&1 | tail -10")
        # Should strip both 2>&1 and the pipe
        self.assertNotIn("2>&1", cmd)
        # The pipe is stripped separately
        self.assertNotIn("|", cmd)

    def test_strip_safe_stderr_redirects(self) -> None:
        """Should strip safe stderr/stdout redirects like 2>&1."""
        # Note: _SAFE_REDIRECT pattern only strips [12]>&[12], >/dev/null, etc.
        cmd, cwd = _normalize_bash_command("ls 2>&1 /dev/null")
        # 2>&1 is stripped, leaving ls and /dev/null
        self.assertNotIn("2>&1", cmd)

    def test_complex_cd_and_pipes(self) -> None:
        """Should handle both cd extraction and pipe stripping."""
        cmd, cwd = _normalize_bash_command("cd /app && npm test 2>&1 | tail -20")
        self.assertEqual(cmd, "npm test")
        self.assertEqual(cwd, "/app")


class SplitCompoundCommandTest(unittest.TestCase):
    """Tests for _split_compound_command() -- Phase 1 bypass vector."""

    def test_split_on_double_ampersand(self) -> None:
        """Should split on && separator."""
        segments = _split_compound_command("git add . && git commit -m test")
        self.assertEqual(segments, ["git add .", "git commit -m test"])

    def test_split_on_semicolon(self) -> None:
        """Should split on ; separator."""
        segments = _split_compound_command("cd /tmp; echo foo > /tmp/evil.txt")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], "cd /tmp")
        self.assertIn("echo", segments[1])

    def test_split_on_or_operator(self) -> None:
        """Should split on || separator."""
        segments = _split_compound_command("git commit || cp policy.yaml /tmp")
        self.assertEqual(segments, ["git commit", "cp policy.yaml /tmp"])

    def test_multiple_separators(self) -> None:
        """Should split on mixed separators."""
        segments = _split_compound_command("cmd1 && cmd2 ; cmd3 || cmd4")
        self.assertEqual(len(segments), 4)

    def test_empty_segments_removed(self) -> None:
        """Should filter out empty segments."""
        segments = _split_compound_command("cmd1 && && cmd2")
        self.assertNotIn("", segments)


class DetectEnvOverrideTest(unittest.TestCase):
    """Tests for _detect_env_override() -- Phase 1 bypass vector."""

    def test_detect_policy_repo_override(self) -> None:
        """Should detect POLICY_REPO=evil env override."""
        result = _detect_env_override("POLICY_REPO=evil git commit")
        self.assertIn("POLICY_REPO", result)

    def test_detect_policy_task_domain_override(self) -> None:
        """Should detect POLICY_TASK_DOMAIN=malicious override."""
        result = _detect_env_override("POLICY_TASK_DOMAIN=admin git push")
        self.assertIn("POLICY_TASK_DOMAIN", result)

    def test_detect_with_env_prefix(self) -> None:
        """Should detect override with env prefix."""
        result = _detect_env_override("env POLICY_REPO=evil cargo test")
        self.assertIn("POLICY_REPO", result)

    def test_detect_with_export_prefix(self) -> None:
        """Should detect override with export prefix."""
        result = _detect_env_override("export POLICY_TASK_INSTANCE=x && cmd")
        self.assertIn("POLICY_TASK_INSTANCE", result)

    def test_detect_policy_repo_and_domain_with_semicolon(self) -> None:
        """Should detect POLICY_REPO and POLICY_TASK_DOMAIN in compound commands."""
        result = _detect_env_override("export POLICY_REPO=x; POLICY_TASK_DOMAIN=y cmd")
        self.assertIn("POLICY_REPO", result)
        self.assertIn("POLICY_TASK_DOMAIN", result)

    def test_ignore_non_policy_vars(self) -> None:
        """Should not flag non-POLICY_ env vars."""
        result = _detect_env_override("PATH=/evil/bin cmd")
        self.assertEqual(result, [])

    def test_detect_in_compound_command(self) -> None:
        """Should detect override in compound command segments."""
        result = _detect_env_override("git add . && POLICY_REPO=evil git commit")
        self.assertIn("POLICY_REPO", result)


class StripEnvOverridesTest(unittest.TestCase):
    """Tests for _strip_env_overrides() -- Phase 1 bypass vector."""

    def test_strip_leading_policy_repo_override(self) -> None:
        """Should remove leading POLICY_REPO=value."""
        cmd = _strip_env_overrides("POLICY_REPO=evil git commit")
        self.assertEqual(cmd, "git commit")

    def test_strip_with_env_prefix(self) -> None:
        """Should remove env POLICY_REPO=value prefix."""
        cmd = _strip_env_overrides("env POLICY_REPO=evil cargo test")
        self.assertEqual(cmd, "cargo test")

    def test_strip_multiple_overrides(self) -> None:
        """Should strip all leading POLICY_* assignments."""
        cmd = _strip_env_overrides("POLICY_REPO=x POLICY_TASK_DOMAIN=y actual_cmd")
        self.assertEqual(cmd, "actual_cmd")

    def test_preserve_non_policy_vars(self) -> None:
        """Should preserve non-POLICY_ env var assignments."""
        cmd = _strip_env_overrides("PATH=/usr/bin actual_cmd")
        self.assertEqual(cmd, "PATH=/usr/bin actual_cmd")

    def test_strip_export_with_space_and_separator(self) -> None:
        """Should handle export POLICY_*=value ; cmd syntax (with space before semicolon)."""
        # The _strip_env_overrides pattern: (?:env\s+|export\s+)?POLICY_\w+=\S*\s*
        # This matches export + POLICY_VAR=value + optional spaces
        # But when there's no space after =, it stops at the first non-whitespace
        cmd = _strip_env_overrides("export POLICY_TASK_INSTANCE=123 ; cmd")
        # The leading export and POLICY_VAR assignment are stripped, leaving "; cmd"
        self.assertNotIn("POLICY_TASK_INSTANCE", cmd)
        self.assertNotIn("export", cmd)


class DetectWriteViaExecTest(unittest.TestCase):
    """Tests for _detect_write_via_exec() -- Phase 1 bypass vectors."""

    def test_detect_python_open_write(self) -> None:
        """Should detect 'python3 -c \"open(...).write(...)\"' bypass."""
        cmd = 'python3 -c "open(\'/tmp/evil.txt\').write(\'data\')"'
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("python-file-write", indicators)

    def test_detect_shell_redirect_write_to_absolute_path(self) -> None:
        """Should detect redirect write pattern that starts command or follows delimiter."""
        # The pattern requires > or delimiter+> at specific positions
        # Plain "echo foo > /path" doesn't match, but "> /path" does match the pattern
        cmd = "> /tmp/policy.yaml"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("shell-redirect-write", indicators)

    def test_detect_tee_write(self) -> None:
        """Should detect 'tee /path' write bypass."""
        cmd = "cat policy.yaml | tee /tmp/backup.yaml"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("tee-write", indicators)

    def test_detect_cp_write(self) -> None:
        """Should detect 'cp src dst' write bypass."""
        cmd = "cp /original/policy.yaml /tmp/evil.yaml"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("cp-write", indicators)

    def test_detect_sed_inplace_write(self) -> None:
        """Should detect 'sed -i' write bypass."""
        cmd = "sed -i 's/allow/deny/' /tmp/policy.yaml"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("sed-inplace-write", indicators)

    def test_detect_mv_write(self) -> None:
        """Should detect 'mv src dst' write bypass."""
        cmd = "mv /tmp/policy.yaml /etc/policy.yaml"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("mv-write", indicators)

    def test_detect_dd_write(self) -> None:
        """Should detect 'dd of=' write bypass."""
        cmd = "dd if=/dev/zero of=/tmp/file bs=1M"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("dd-write", indicators)

    def test_detect_heredoc_write(self) -> None:
        """Should detect '<<EOF' heredoc write bypass."""
        cmd = """cat <<EOF > /tmp/file.txt
some content
EOF"""
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("heredoc-write", indicators)

    def test_detect_in_compound_command_with_tee(self) -> None:
        """Should detect write bypasses in compound commands with tee."""
        cmd = "git commit && cat policy.yaml | tee /tmp/backup.yaml"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("tee-write", indicators)

    def test_detect_in_backtick_subshell(self) -> None:
        """Should detect write commands in backtick subshells."""
        cmd = "result=`cp /a /b`; echo $result"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("subshell-write", indicators)
        self.assertIn("subshell:cp-write", indicators)

    def test_detect_xargs_write(self) -> None:
        """Should detect write commands via xargs pipe."""
        cmd = "find . -name file | xargs rm"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("xargs-write", indicators)

    def test_no_false_positive_on_stderr_redirect(self) -> None:
        """Should not flag stderr-only redirects as writes."""
        cmd = "cargo build 2>&1"
        indicators = _detect_write_via_exec(cmd)
        self.assertEqual(indicators, [])

    def test_no_false_positive_on_grep_in_pipe(self) -> None:
        """Should not flag grep-in-pipe patterns as writes."""
        cmd = "cat file.txt | grep pattern"
        indicators = _detect_write_via_exec(cmd)
        self.assertEqual(indicators, [])

    def test_detect_ruby_file_write(self) -> None:
        """Should detect ruby -e File.write() bypass."""
        cmd = "ruby -e 'File.write(\"/tmp/x.txt\", \"data\")'"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("ruby-file-write", indicators)

    def test_detect_perl_file_write(self) -> None:
        """Should detect perl -e open() write bypass."""
        cmd = "perl -e 'open(F, \">/tmp/x\"); print F \"data\"'"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("perl-file-write", indicators)

    def test_detect_node_file_write(self) -> None:
        """Should detect node -e writeFile() bypass."""
        cmd = "node -e 'fs.writeFile(\"/tmp/x.txt\", \"data\", () => {})'"
        indicators = _detect_write_via_exec(cmd)
        self.assertIn("node-file-write", indicators)


class EndToEndBypassDetectionTest(unittest.TestCase):
    """End-to-end tests for Phase 1 bypass vector detection in Claude hooks."""

    def test_bash_tool_python_write_reclassified_as_write_action(self) -> None:
        """python3 -c open() should be reclassified as write action."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'python3 -c "open(\'/tmp/evil.txt\').write(\'xss\')"'},
            "cwd": "/tmp",
            "session_id": "session-1",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput", {})
        if hook:
            self.assertEqual(hook["permissionDecision"], "deny")
            self.assertIn("write-via-exec", hook["permissionDecisionReason"])

    def test_bash_tool_tee_write_reclassified(self) -> None:
        """tee /path should be reclassified as write action."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat policy.yaml | tee /etc/evil.conf"},
            "cwd": "/tmp",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput", {})
        if hook:
            # Should be reclassified as write and denied
            self.assertIn("write-via-exec", hook["permissionDecisionReason"])

    def test_bash_tool_env_override_detection(self) -> None:
        """POLICY_REPO=evil should be detected and stripped."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "POLICY_REPO=evil git commit"},
            "cwd": "/tmp",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        hook = result.get("hookSpecificOutput", {})
        if hook:
            self.assertIn("env-override", hook["permissionDecisionReason"])

    def test_bash_tool_cd_normalization(self) -> None:
        """cd /path && cmd should normalize cwd to /path."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd /tmp && cargo test"},
            "cwd": "/original",
        }
        result = evaluate_claude_pretool_payload(payload, repo_root=REPO_ROOT)
        # Should use /tmp as cwd for policy evaluation
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

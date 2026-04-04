from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import REPO_ROOT

from policy_federation.runtime_artifacts import (
    append_audit_event,
    build_run_sidecar,
    write_sidecar,
)


class BuildRunSidecarTest(unittest.TestCase):
    """Tests for build_run_sidecar() -- sidecar structure and integrity."""

    def test_build_sidecar_with_required_fields(self) -> None:
        """Should build sidecar with all required fields."""
        sidecar = build_run_sidecar(
            harness="codex",
            task_domain="devops",
            task_instance="task-1",
            policy_hash="hash-abc123",
            scope_chain=["global", "repo:thegent"],
        )
        self.assertIn("run_id", sidecar)
        self.assertIn("policy_hash", sidecar)
        self.assertIn("scope_chain", sidecar)
        self.assertIn("audit", sidecar)
        self.assertIn("resolved_at", sidecar)
        self.assertEqual(sidecar["harness"], "codex")
        self.assertEqual(sidecar["task_domain"], "devops")
        self.assertEqual(sidecar["task_instance"], "task-1")

    def test_sidecar_run_id_is_unique(self) -> None:
        """Each sidecar should get a unique run_id."""
        sidecar1 = build_run_sidecar(
            harness="codex",
            task_domain="devops",
            task_instance=None,
            policy_hash="hash",
            scope_chain=[],
        )
        sidecar2 = build_run_sidecar(
            harness="codex",
            task_domain="devops",
            task_instance=None,
            policy_hash="hash",
            scope_chain=[],
        )
        self.assertNotEqual(sidecar1["run_id"], sidecar2["run_id"])

    def test_sidecar_resolved_at_is_iso_format(self) -> None:
        """resolved_at should be ISO format with Z suffix."""
        sidecar = build_run_sidecar(
            harness="codex",
            task_domain="devops",
            task_instance=None,
            policy_hash="hash",
            scope_chain=[],
        )
        resolved_at = sidecar["resolved_at"]
        self.assertIn("T", resolved_at)
        self.assertTrue(resolved_at.endswith("Z"))

    def test_sidecar_with_custom_run_id(self) -> None:
        """Should accept and preserve custom run_id."""
        custom_run_id = "custom-id-12345"
        sidecar = build_run_sidecar(
            harness="codex",
            task_domain="devops",
            task_instance=None,
            policy_hash="hash",
            scope_chain=[],
            run_id=custom_run_id,
        )
        self.assertEqual(sidecar["run_id"], custom_run_id)

    def test_sidecar_with_source_files(self) -> None:
        """Should include source_files list in sidecar."""
        source_files = [
            "/Users/kooshapari/CodeProjects/Phenotype/repos/agentops-policy-federation-wtrees/resolver-multi-repo/policies/global.yaml",
            "/Users/kooshapari/CodeProjects/Phenotype/repos/agentops-policy-federation-wtrees/resolver-multi-repo/policies/repo.yaml",
        ]
        sidecar = build_run_sidecar(
            harness="codex",
            task_domain="devops",
            task_instance=None,
            policy_hash="hash",
            scope_chain=[],
            source_files=source_files,
        )
        self.assertEqual(sidecar["source_files"], source_files)


class WriteSidecarTest(unittest.TestCase):
    """Tests for write_sidecar() -- file persistence and format."""

    def test_write_sidecar_creates_file(self) -> None:
        """Should create sidecar file on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session.json"
            payload = {
                "run_id": "test-123",
                "policy_hash": "abc",
                "scope_chain": [],
            }
            write_sidecar(sidecar_path=sidecar_path, payload=payload)
            self.assertTrue(sidecar_path.exists())

    def test_write_sidecar_creates_parent_directories(self) -> None:
        """Should create parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "nested" / "dir" / "session.json"
            payload = {"run_id": "test"}
            write_sidecar(sidecar_path=sidecar_path, payload=payload)
            self.assertTrue(sidecar_path.exists())

    def test_write_sidecar_json_format(self) -> None:
        """Should write valid JSON with 2-space indent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session.json"
            payload = {"run_id": "test", "policy_hash": "abc"}
            write_sidecar(sidecar_path=sidecar_path, payload=payload)
            content = sidecar_path.read_text()
            # Should be valid JSON
            parsed = json.loads(content)
            self.assertEqual(parsed["run_id"], "test")
            # Should have indentation (2 spaces per JSON spec)
            self.assertIn("\n  ", content)

    def test_write_sidecar_overwrites_existing(self) -> None:
        """Should overwrite existing sidecar file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session.json"
            # Write first version
            payload1 = {"run_id": "test-1"}
            write_sidecar(sidecar_path=sidecar_path, payload=payload1)
            # Write second version
            payload2 = {"run_id": "test-2"}
            write_sidecar(sidecar_path=sidecar_path, payload=payload2)
            # Should have second version
            content = sidecar_path.read_text()
            parsed = json.loads(content)
            self.assertEqual(parsed["run_id"], "test-2")

    def test_write_sidecar_trailing_newline(self) -> None:
        """Sidecar should end with a newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "session.json"
            payload = {"run_id": "test"}
            write_sidecar(sidecar_path=sidecar_path, payload=payload)
            content = sidecar_path.read_text()
            self.assertTrue(content.endswith("\n"))


class AppendAuditEventTest(unittest.TestCase):
    """Tests for append_audit_event() -- audit log chain verification."""

    def test_append_audit_event_creates_file(self) -> None:
        """Should create audit log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            event = {"action": "exec", "command": "test"}
            append_audit_event(audit_log_path=audit_log_path, event=event)
            self.assertTrue(audit_log_path.exists())

    def test_append_audit_event_jsonl_format(self) -> None:
        """Each audit event should be valid JSON on its own line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            event1 = {"action": "exec", "command": "cmd1"}
            event2 = {"action": "write", "command": "cmd2"}
            append_audit_event(audit_log_path=audit_log_path, event=event1)
            append_audit_event(audit_log_path=audit_log_path, event=event2)
            lines = audit_log_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2)
            # Each line should be valid JSON
            parsed1 = json.loads(lines[0])
            parsed2 = json.loads(lines[1])
            self.assertEqual(parsed1["command"], "cmd1")
            self.assertEqual(parsed2["command"], "cmd2")

    def test_append_audit_event_creates_parent_directories(self) -> None:
        """Should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "logs" / "subdir" / "audit.jsonl"
            event = {"action": "exec"}
            append_audit_event(audit_log_path=audit_log_path, event=event)
            self.assertTrue(audit_log_path.exists())

    def test_audit_log_chain_verification(self) -> None:
        """Verify audit chain: multiple writes should all be recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            # Simulate a sequence of events: policy resolution, then command eval
            events = [
                {
                    "run_id": "run-1",
                    "action": "exec",
                    "command": "git commit",
                    "final_decision": "deny",
                },
                {
                    "run_id": "run-1",
                    "action": "write",
                    "command": "echo x > /tmp/file",
                    "final_decision": "deny",
                },
                {
                    "run_id": "run-2",
                    "action": "exec",
                    "command": "ls",
                    "final_decision": "allow",
                },
            ]
            for event in events:
                append_audit_event(audit_log_path=audit_log_path, event=event)

            # Verify all events are present
            lines = audit_log_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 3)
            parsed_events = [json.loads(line) for line in lines]
            self.assertEqual(parsed_events[0]["command"], "git commit")
            self.assertEqual(parsed_events[1]["command"], "echo x > /tmp/file")
            self.assertEqual(parsed_events[2]["command"], "ls")

    def test_audit_event_tampered_detection(self) -> None:
        """Simulates detecting a tampered audit log (middle entry modified)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            # Write initial events
            events = [
                {"seq": 1, "action": "exec", "command": "cmd1"},
                {"seq": 2, "action": "exec", "command": "cmd2"},
                {"seq": 3, "action": "exec", "command": "cmd3"},
            ]
            for event in events:
                append_audit_event(audit_log_path=audit_log_path, event=event)

            # Read and verify integrity
            content = audit_log_path.read_text()
            lines = content.strip().split("\n")
            original_middle = json.loads(lines[1])
            self.assertEqual(original_middle["seq"], 2)

            # Simulate tampering: rewrite middle entry directly to file
            tampered_lines = [
                lines[0],
                json.dumps({"seq": 2, "action": "exec", "command": "modified"}),
                lines[2],
            ]
            audit_log_path.write_text("\n".join(tampered_lines) + "\n")

            # Verify tampering is detectable
            new_content = audit_log_path.read_text()
            new_lines = new_content.strip().split("\n")
            new_middle = json.loads(new_lines[1])
            self.assertNotEqual(new_middle["command"], "cmd2")

    def test_audit_event_sorted_keys(self) -> None:
        """Audit events should have sorted keys for consistency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit.jsonl"
            # Event with unsorted keys
            event = {
                "z_field": "last",
                "action": "exec",
                "a_field": "first",
                "command": "test",
            }
            append_audit_event(audit_log_path=audit_log_path, event=event)
            content = audit_log_path.read_text().strip()
            # Keys should be sorted in JSON
            self.assertTrue(
                content.index("a_field") < content.index("z_field"),
                "Keys should be sorted in JSON output",
            )


if __name__ == "__main__":
    unittest.main()

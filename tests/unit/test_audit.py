"""Tests for audit log reading, filtering, and verification."""

from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401 -- setup sys.path
from policy_federation.runtime_artifacts import (
    filter_audit_events,
    read_audit_log,
    verify_audit_chain,
)


class ReadAuditLogTest(unittest.TestCase):
    """Tests for read_audit_log()."""

    def test_read_empty_log(self) -> None:
        """Should return empty list for non-existent log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            events = read_audit_log(log_path)
            assert events == []

    def test_read_single_event(self) -> None:
        """Should read a single JSONL event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            event = {
                "run_id": "run-1",
                "action": "exec",
                "final_decision": "allow",
                "actor": "user1",
            }
            log_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            events = read_audit_log(log_path)
            assert len(events) == 1
            assert events[0]["run_id"] == "run-1"

    def test_read_multiple_events(self) -> None:
        """Should read multiple JSONL events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            events_to_write = [
                {"run_id": "run-1", "action": "exec", "final_decision": "allow"},
                {"run_id": "run-2", "action": "write", "final_decision": "deny"},
                {"run_id": "run-3", "action": "network", "final_decision": "ask"},
            ]
            with log_path.open("w", encoding="utf-8") as f:
                for evt in events_to_write:
                    f.write(json.dumps(evt) + "\n")

            events = read_audit_log(log_path)
            assert len(events) == 3
            assert events[0]["run_id"] == "run-1"
            assert events[1]["run_id"] == "run-2"
            assert events[2]["run_id"] == "run-3"

    def test_read_log_with_blank_lines(self) -> None:
        """Should skip blank lines in JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            content = (
                '{"run_id": "run-1", "action": "exec", "final_decision": "allow"}\n'
                "\n"
                '{"run_id": "run-2", "action": "write", "final_decision": "deny"}\n'
            )
            log_path.write_text(content, encoding="utf-8")

            events = read_audit_log(log_path)
            assert len(events) == 2

    def test_read_log_with_malformed_json(self) -> None:
        """Should skip malformed JSON lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            content = (
                '{"run_id": "run-1", "action": "exec", "final_decision": "allow"}\n'
                "not valid json\n"
                '{"run_id": "run-2", "action": "write", "final_decision": "deny"}\n'
            )
            log_path.write_text(content, encoding="utf-8")

            events = read_audit_log(log_path)
            assert len(events) == 2
            assert events[0]["run_id"] == "run-1"
            assert events[1]["run_id"] == "run-2"


class VerifyAuditChainTest(unittest.TestCase):
    """Tests for verify_audit_chain()."""

    def test_verify_empty_chain(self) -> None:
        """Should mark empty chain as valid."""
        result = verify_audit_chain([])
        assert result["valid"]
        assert result["events_checked"] == 0

    def test_verify_valid_chain(self) -> None:
        """Should verify a valid chain."""
        events = [
            {
                "run_id": "run-1",
                "action": "exec",
                "final_decision": "allow",
            },
            {
                "run_id": "run-2",
                "action": "write",
                "final_decision": "deny",
            },
        ]
        result = verify_audit_chain(events)
        assert result["valid"]
        assert result["events_checked"] == 2

    def test_verify_chain_missing_run_id(self) -> None:
        """Should detect missing run_id."""
        events = [
            {"action": "exec", "final_decision": "allow"},  # missing run_id
        ]
        result = verify_audit_chain(events)
        assert not result["valid"]
        assert len(result["invalid_events"]) == 1
        assert "run_id" in result["invalid_events"][0]["missing_fields"]

    def test_verify_chain_missing_action(self) -> None:
        """Should detect missing action."""
        events = [
            {"run_id": "run-1", "final_decision": "allow"},  # missing action
        ]
        result = verify_audit_chain(events)
        assert not result["valid"]
        assert "action" in result["invalid_events"][0]["missing_fields"]

    def test_verify_chain_missing_decision(self) -> None:
        """Should detect missing final_decision."""
        events = [
            {"run_id": "run-1", "action": "exec"},  # missing final_decision
        ]
        result = verify_audit_chain(events)
        assert not result["valid"]
        assert "final_decision" in result["invalid_events"][0]["missing_fields"]


class FilterAuditEventsTest(unittest.TestCase):
    """Tests for filter_audit_events()."""

    def setUp(self) -> None:
        """Set up test events."""
        self.events = [
            {
                "run_id": "run-1",
                "action": "exec",
                "final_decision": "allow",
                "actor": "alice",
                "timestamp": "2024-01-15T10:00:00Z",
            },
            {
                "run_id": "run-2",
                "action": "write",
                "final_decision": "deny",
                "actor": "bob",
                "timestamp": "2024-01-15T11:00:00Z",
            },
            {
                "run_id": "run-3",
                "action": "exec",
                "final_decision": "ask",
                "actor": "alice",
                "timestamp": "2024-01-15T12:00:00Z",
            },
            {
                "run_id": "run-4",
                "action": "network",
                "final_decision": "allow",
                "actor": "charlie",
                "timestamp": "2024-01-15T13:00:00Z",
            },
        ]

    def test_filter_by_action(self) -> None:
        """Should filter by action."""
        filtered = filter_audit_events(self.events, action="exec")
        assert len(filtered) == 2
        assert all(e["action"] == "exec" for e in filtered)

    def test_filter_by_decision(self) -> None:
        """Should filter by decision."""
        filtered = filter_audit_events(self.events, decision="allow")
        assert len(filtered) == 2
        assert all(e["final_decision"] == "allow" for e in filtered)

    def test_filter_by_actor_substring(self) -> None:
        """Should filter by actor substring."""
        filtered = filter_audit_events(self.events, actor_pattern="alice")
        assert len(filtered) == 2
        assert all(e["actor"] == "alice" for e in filtered)

    def test_filter_by_actor_regex(self) -> None:
        """Should filter by actor regex pattern."""
        filtered = filter_audit_events(
            self.events, actor_pattern="^[ab]",
        )  # alice or bob
        assert len(filtered) == 3

    def test_filter_by_since(self) -> None:
        """Should filter by since time."""
        since = datetime.datetime.fromisoformat("2024-01-15T11:30:00+00:00")
        filtered = filter_audit_events(self.events, since=since)
        assert len(filtered) == 2  # events at 12:00 and 13:00

    def test_filter_by_until(self) -> None:
        """Should filter by until time."""
        until = datetime.datetime.fromisoformat("2024-01-15T11:30:00+00:00")
        filtered = filter_audit_events(self.events, until=until)
        assert len(filtered) == 2  # events at 10:00 and 11:00

    def test_filter_by_since_and_until(self) -> None:
        """Should filter by both since and until."""
        since = datetime.datetime.fromisoformat("2024-01-15T10:30:00+00:00")
        until = datetime.datetime.fromisoformat("2024-01-15T12:30:00+00:00")
        filtered = filter_audit_events(self.events, since=since, until=until)
        assert len(filtered) == 2  # events at 11:00 and 12:00

    def test_filter_combined(self) -> None:
        """Should filter by multiple criteria."""
        filtered = filter_audit_events(
            self.events,
            action="exec",
            decision="allow",
            actor_pattern="alice",
        )
        assert len(filtered) == 1
        assert filtered[0]["run_id"] == "run-1"

    def test_filter_with_missing_timestamp(self) -> None:
        """Should include events without timestamp when filtering by time."""
        events = [
            {"run_id": "run-1", "action": "exec", "final_decision": "allow"},
            {
                "run_id": "run-2",
                "action": "write",
                "final_decision": "deny",
                "timestamp": "2024-01-15T11:00:00Z",
            },
        ]
        since = datetime.datetime.fromisoformat("2024-01-15T10:00:00+00:00")
        filtered = filter_audit_events(events, since=since)
        # Both events included: one without timestamp, one matching
        assert len(filtered) == 2

    def test_filter_with_missing_actor(self) -> None:
        """Should exclude events without actor when filtering by actor."""
        events = [
            {"run_id": "run-1", "action": "exec", "final_decision": "allow"},
            {
                "run_id": "run-2",
                "action": "write",
                "final_decision": "deny",
                "actor": "bob",
            },
        ]
        filtered = filter_audit_events(events, actor_pattern="bob")
        assert len(filtered) == 1
        assert filtered[0]["actor"] == "bob"


if __name__ == "__main__":
    unittest.main()

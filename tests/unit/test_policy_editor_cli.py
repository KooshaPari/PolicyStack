"""Integration tests for policy editor CLI commands."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from io import StringIO
import sys

import pytest
import yaml

from support import CLI_SRC


@pytest.fixture
def temp_policy_file():
    """Create a temporary policy file for testing."""
    content = {
        "version": "1.0",
        "id": "test/policy",
        "scope": "system",
        "policy": {
            "authorization": {
                "defaults": {
                    "exec": "ask",
                },
                "rules": [
                    {
                        "id": "base-read-only",
                        "effect": "allow",
                        "actions": ["read"],
                        "priority": 0,
                    }
                ],
            }
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(content, f)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_audit_log():
    """Create a temporary audit log file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_cli_add_rule_simple(temp_policy_file):
    """Test add-rule CLI command with simple rule."""
    from policy_federation.cli import main

    sys.argv = [
        "policyctl",
        "add-rule",
        "--file", str(temp_policy_file),
        "--id", "deny-write",
        "--effect", "deny",
        "--priority", "100",
        "--actions", "write",
    ]

    # Capture output
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    result = json.loads(output)
    assert result["result"] == "rule-added"
    assert result["rule_id"] == "deny-write"

    # Verify file was updated
    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)
    rules = doc["policy"]["authorization"]["rules"]
    assert len(rules) == 2
    assert rules[1]["id"] == "deny-write"
    assert rules[1]["effect"] == "deny"


def test_cli_add_rule_with_patterns(temp_policy_file):
    """Test add-rule CLI command with match patterns."""
    from policy_federation.cli import main

    sys.argv = [
        "policyctl",
        "add-rule",
        "--file", str(temp_policy_file),
        "--id", "ask-pip-install",
        "--effect", "ask",
        "--priority", "50",
        "--actions", "exec",
        "--command-patterns", "pip install*,npm install*",
    ]

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    result = json.loads(output)
    assert result["result"] == "rule-added"

    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)
    rules = doc["policy"]["authorization"]["rules"]
    added_rule = rules[-1]
    assert added_rule["id"] == "ask-pip-install"
    assert added_rule["match"]["command_patterns"] == ["pip install*", "npm install*"]


def test_cli_remove_rule(temp_policy_file):
    """Test remove-rule CLI command."""
    from policy_federation.cli import main

    # First add a rule
    sys.argv = [
        "policyctl",
        "add-rule",
        "--file", str(temp_policy_file),
        "--id", "temp-rule",
        "--effect", "allow",
        "--priority", "10",
        "--actions", "read",
    ]
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    sys.stdout = old_stdout

    # Then remove it
    sys.argv = [
        "policyctl",
        "remove-rule",
        "--file", str(temp_policy_file),
        "--id", "temp-rule",
    ]
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    result = json.loads(output)
    assert result["result"] == "rule-removed"
    assert result["rule_id"] == "temp-rule"

    # Verify rule was removed
    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)
    rules = doc["policy"]["authorization"]["rules"]
    rule_ids = [r["id"] for r in rules]
    assert "temp-rule" not in rule_ids


def test_cli_add_rule_with_audit_log(temp_policy_file, temp_audit_log):
    """Test that add-rule records audit event."""
    from policy_federation.cli import main

    sys.argv = [
        "policyctl",
        "add-rule",
        "--file", str(temp_policy_file),
        "--id", "audited-rule",
        "--effect", "ask",
        "--priority", "30",
        "--actions", "network",
        "--audit-log-path", str(temp_audit_log),
    ]

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    sys.stdout = old_stdout

    # Verify audit event was recorded
    with temp_audit_log.open() as f:
        events = [json.loads(line) for line in f if line.strip()]

    assert len(events) == 1
    event = events[0]
    assert event["action"] == "policy-rule-add"
    assert event["rule_id"] == "audited-rule"
    assert event["policy_file"] == str(temp_policy_file)
    assert event["effect"] == "ask"
    assert "timestamp" in event


def test_cli_remove_rule_with_audit_log(temp_policy_file, temp_audit_log):
    """Test that remove-rule records audit event."""
    from policy_federation.cli import main

    # Add rule first
    sys.argv = [
        "policyctl",
        "add-rule",
        "--file", str(temp_policy_file),
        "--id", "to-be-removed",
        "--effect", "allow",
        "--priority", "5",
        "--actions", "read",
    ]
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    sys.stdout = old_stdout

    # Remove and log
    sys.argv = [
        "policyctl",
        "remove-rule",
        "--file", str(temp_policy_file),
        "--id", "to-be-removed",
        "--audit-log-path", str(temp_audit_log),
    ]
    sys.stdout = StringIO()
    try:
        main()
    except SystemExit:
        pass
    sys.stdout = old_stdout

    # Verify audit event
    with temp_audit_log.open() as f:
        events = [json.loads(line) for line in f if line.strip()]

    assert len(events) == 1
    event = events[0]
    assert event["action"] == "policy-rule-remove"
    assert event["rule_id"] == "to-be-removed"
    assert "timestamp" in event


def test_cli_diff_simple(temp_policy_file):
    """Test policyctl diff CLI command with simple policy changes."""
    from policy_federation.cli import main

    # Create a before policy
    with temp_policy_file.open() as f:
        before_content = f.read()

    # Create an after policy with a different rule
    after_content = before_content.replace("base-read-only", "new-write-deny")
    after_content = after_content.replace('"read"', '"write"')
    after_content = after_content.replace('"allow"', '"deny"')

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(after_content)
        after_path = Path(f.name)

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        sys.argv = [
            "policyctl",
            "diff",
            str(temp_policy_file),
            str(after_path),
        ]
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    # Should contain JSON output with diff results
    assert "added_rules" in output
    assert "removed_rules" in output
    after_path.unlink()


def test_cli_diff_added_rules(temp_policy_file):
    """Test policyctl diff detects added rules."""
    from policy_federation.cli import main

    # Load the original policy
    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)

    # Create after policy with additional rule
    doc["policy"]["authorization"]["rules"].append({
        "id": "added-rule",
        "effect": "deny",
        "actions": ["write"],
        "priority": 100,
    })

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(doc, f)
        after_path = Path(f.name)

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        sys.argv = [
            "policyctl",
            "diff",
            str(temp_policy_file),
            str(after_path),
        ]
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    # Parse the JSON output - find the JSON object in the output
    # The output contains colored text and JSON, find the JSON part
    import re
    json_match = re.search(r'\{[\s\S]*\}', output)
    assert json_match, f"No JSON found in output: {output}"
    result = json.loads(json_match.group())

    assert len(result["added_rules"]) == 1
    assert result["added_rules"][0]["id"] == "added-rule"
    after_path.unlink()


def test_cli_diff_removed_rules(temp_policy_file):
    """Test policyctl diff detects removed rules."""
    from policy_federation.cli import main

    # Load the original policy
    with temp_policy_file.open() as f:
        doc = yaml.safe_load(f)

    # Create after policy with rule removed
    doc["policy"]["authorization"]["rules"] = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(doc, f)
        after_path = Path(f.name)

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        sys.argv = [
            "policyctl",
            "diff",
            str(temp_policy_file),
            str(after_path),
        ]
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    # Parse the JSON output - find the JSON object in the output
    import re
    json_match = re.search(r'\{[\s\S]*\}', output)
    assert json_match, f"No JSON found in output: {output}"
    result = json.loads(json_match.group())

    assert len(result["removed_rules"]) == 1
    assert result["removed_rules"][0]["id"] == "base-read-only"
    after_path.unlink()


@pytest.fixture
def temp_audit_log_with_events():
    """Create a temporary audit log file with sample events."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        events = [
            {
                "timestamp": "2024-01-15T10:00:00+00:00",
                "run_id": "run-1",
                "action": "exec",
                "final_decision": "allow",
                "actor": "alice",
            },
            {
                "timestamp": "2024-01-15T11:00:00+00:00",
                "run_id": "run-2",
                "action": "write",
                "final_decision": "deny",
                "actor": "bob",
            },
            {
                "timestamp": "2024-01-15T12:00:00+00:00",
                "run_id": "run-3",
                "action": "exec",
                "final_decision": "ask",
                "actor": "alice",
            },
            {
                "timestamp": "2024-01-15T13:00:00+00:00",
                "run_id": "run-4",
                "action": "network",
                "final_decision": "allow",
                "actor": "charlie",
            },
        ]
        for event in events:
            f.write(json.dumps(event) + "\n")
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_cli_audit_with_summary(temp_audit_log_with_events):
    """Test policyctl audit --summary output format."""
    from policy_federation.cli import main

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        sys.argv = [
            "policyctl",
            "audit",
            "--log-path", str(temp_audit_log_with_events),
            "--summary",
        ]
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    result = json.loads(output)
    assert result["total"] == 4
    assert result["by_decision"]["allow"] == 2
    assert result["by_decision"]["deny"] == 1
    assert result["by_decision"]["ask"] == 1
    assert result["by_action"]["exec"] == 2
    assert result["by_action"]["write"] == 1
    assert result["by_action"]["network"] == 1


def test_cli_audit_summary_format_complete(temp_audit_log_with_events):
    """Test that audit summary includes all required fields."""
    from policy_federation.cli import main

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        sys.argv = [
            "policyctl",
            "audit",
            "--log-path", str(temp_audit_log_with_events),
            "--summary",
        ]
        main()
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    result = json.loads(output)
    # Verify summary structure
    assert "total" in result
    assert "by_decision" in result
    assert "by_action" in result
    # Verify all decision types present
    assert "allow" in result["by_decision"]
    assert "deny" in result["by_decision"]
    assert "ask" in result["by_decision"]


def test_cli_audit_verify_chain_valid(temp_audit_log_with_events):
    """Test policyctl audit --verify-chain with valid chain."""
    from policy_federation.cli import main

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        sys.argv = [
            "policyctl",
            "audit",
            "--log-path", str(temp_audit_log_with_events),
            "--verify-chain",
        ]
        main()
    except SystemExit as e:
        exit_code = e.code
    else:
        exit_code = 0
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    # Valid chain should not raise SystemExit with code 1
    assert exit_code == 0 or exit_code is None


def test_cli_audit_verify_chain_invalid():
    """Test policyctl audit --verify-chain with invalid chain."""
    from policy_federation.cli import main

    # Create an audit log with invalid events (missing required fields)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Event missing run_id
        f.write(json.dumps({"action": "exec", "final_decision": "allow"}) + "\n")
        temp_path = Path(f.name)

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    exit_code = None
    try:
        sys.argv = [
            "policyctl",
            "audit",
            "--log-path", str(temp_path),
            "--verify-chain",
        ]
        main()
    except SystemExit as e:
        exit_code = e.code
    finally:
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        temp_path.unlink()

    # Invalid chain should exit with code 1
    assert exit_code == 1 or "Chain verification" in output

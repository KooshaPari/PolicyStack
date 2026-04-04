"""Tests for policy gap detection."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import support  # noqa: F401 -- setup sys.path

from policy_federation.gap_detector import (
    GapReport,
    detect_gaps,
    format_gap_report,
)


def _write_audit(path: Path, events: list[dict]) -> None:
    with path.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


class TestDetectGaps:
    def test_empty_log(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            audit_path = Path(f.name)
        report = detect_gaps(
            audit_log_path=audit_path,
            repo_root=Path("/nonexistent"),
        )
        assert report.high_frequency_asks == []
        audit_path.unlink()

    def test_detects_high_frequency_asks(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(15):
                f.write(
                    json.dumps({
                        "run_id": f"r{i}",
                        "action": "exec",
                        "command": f"ls -la /path/{i}",
                        "final_decision": "ask",
                    })
                    + "\n"
                )
            audit_path = Path(f.name)

        report = detect_gaps(
            audit_log_path=audit_path,
            repo_root=Path("/nonexistent"),
            min_ask_frequency=3,
        )
        assert len(report.high_frequency_asks) > 0
        assert report.high_frequency_asks[0]["count"] >= 3
        audit_path.unlink()


class TestFormatGapReport:
    def test_empty_report(self) -> None:
        report = GapReport()
        output = format_gap_report(report)
        assert "No gaps detected" in output

    def test_report_with_gaps(self) -> None:
        report = GapReport(
            high_frequency_asks=[{
                "command_prefix": "ls -la",
                "count": 47,
                "severity": "HIGH",
                "suggestion": "Consider adding allow rule",
            }],
        )
        output = format_gap_report(report)
        assert "HIGH" in output
        assert "47" in output
        assert "ls -la" in output

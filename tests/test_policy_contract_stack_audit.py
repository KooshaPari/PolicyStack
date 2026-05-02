from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "lane4_policy_contract_pr_stack_audit.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "lane4_policy_contract_pr_stack_audit", SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec
    assert spec.loader
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


MOD = _load_audit_module()


def _fake_pr(number: int, *, head: str, base: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "number": number,
        "title": f"stacked-pr-{number}",
        "state": "OPEN",
        "isDraft": False,
        "labels": [],
        "body": "",
        "headRefName": head,
        "baseRefName": base,
        "url": f"https://example.test/pull/{number}",
    }
    payload.update(extra)
    return payload


def test_lane4_stacked_pr_candidates_are_ordered_stably() -> None:
    prs = [
        _fake_pr(20, head="stack/feature-2", base="main"),
        _fake_pr(11, head="stack/feature-1", base="stack/feature-2"),
        _fake_pr(1, head="stack/feature-0", base="stack/feature-1"),
    ]
    stacked, missing, summary = MOD.find_stacked_and_token_findings(
        prs,
        repo="owner/repo",
        label_name="approval-token",
        token_patterns=[MOD.DEFAULT_APPROVAL_TOKEN_PATTERNS[0]],
        check_comments=False,
    )

    assert [entry["number"] for entry in stacked] == [1, 11, 20]
    assert [entry["number"] for entry in missing] == [1, 11, 20]
    assert summary.stacked_prs == 3
    assert summary.missing_token_count == 3
    assert summary.comment_scan_errors == 0
    assert summary.missing_token_findings_by_source == {"none": 3}


def _run_main(
    monkeypatch,
    *,
    apply: bool = False,
    summary_kwargs: dict[str, Any] | None = None,
    apply_actions: list[dict[str, Any]] | None = None,
) -> int:
    if summary_kwargs is None:
        summary_kwargs = {
            "repo": "owner/repo",
            "scanned_prs": 2,
            "stacked_prs": 1,
            "missing_token_count": 1,
            "comment_scan_errors": 0,
            "missing_token_findings_by_source": {"none": 1},
        }
    if apply_actions is None:
        apply_actions = [{"number": 1, "applied": True, "action": "commented"}]

    monkeypatch.setattr(
        MOD,
        "list_open_prs",
        lambda _repo, _limit: (
            True,
            [_fake_pr(1, head="stack/feature", base="main")],
            None,
        ),
    )
    monkeypatch.setattr(
        MOD,
        "find_stacked_and_token_findings",
        lambda *args, **kwargs: (
            [{"number": 1}],
            [
                {
                    "number": 1,
                    "commentCheckError": summary_kwargs["comment_scan_errors"] > 0,
                },
            ],
            MOD.FindingsSummary(**summary_kwargs),
        ),
    )
    if apply:
        monkeypatch.setattr(
            MOD,
            "apply_remediation",
            lambda *_args, **_kwargs: apply_actions,
        )

    args = ["lane4-policy-audit", "--repo", "owner/repo"]
    if apply:
        args.append("--apply")
    monkeypatch.setattr(sys, "argv", args)
    return MOD.main()


def test_main_returns_missing_token_exit_code_for_read_only_run(monkeypatch) -> None:
    assert (
        _run_main(
            monkeypatch,
            apply=False,
            summary_kwargs={
                "repo": "owner/repo",
                "scanned_prs": 2,
                "stacked_prs": 1,
                "missing_token_count": 1,
                "comment_scan_errors": 0,
                "missing_token_findings_by_source": {"label": 1},
            },
        )
        == 4
    )


def test_main_returns_comment_scan_error_exit_code(monkeypatch) -> None:
    assert (
        _run_main(
            monkeypatch,
            apply=False,
            summary_kwargs={
                "repo": "owner/repo",
                "scanned_prs": 2,
                "stacked_prs": 1,
                "missing_token_count": 0,
                "comment_scan_errors": 1,
                "missing_token_findings_by_source": {},
            },
        )
        == 2
    )


def test_main_returns_remediation_failure_exit_code(monkeypatch) -> None:
    assert (
        _run_main(
            monkeypatch,
            apply=True,
            summary_kwargs={
                "repo": "owner/repo",
                "scanned_prs": 2,
                "stacked_prs": 1,
                "missing_token_count": 1,
                "comment_scan_errors": 0,
                "missing_token_findings_by_source": {"body": 1},
            },
            apply_actions=[
                {
                    "number": 1,
                    "applied": False,
                    "action": "commented",
                    "error": "gh",
                },
            ],
        )
        == 3
    )


def test_find_stacked_records_collects_mixed_comment_error_with_partial_data(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MOD,
        "list_pr_comments_all",
        lambda _repo, pr_number: (
            pr_number != 7,
            [{"body": "manual override"}] if pr_number != 7 else [],
            "issue_comments: throttled" if pr_number == 7 else None,
        ),
    )

    _stacked, missing, summary = MOD.find_stacked_and_token_findings(
        [
            _fake_pr(7, head="stack/feature-7", base="main"),
            _fake_pr(8, head="stack/feature-8", base="stack/feature-7"),
            _fake_pr(9, head="stack/feature-9", base="stack/feature-8"),
        ],
        repo="owner/repo",
        label_name="approval-token",
        token_patterns=[MOD.DEFAULT_APPROVAL_TOKEN_PATTERNS[0]],
        check_comments=True,
    )

    assert summary.stacked_prs == 3
    assert summary.missing_token_count == 3
    assert summary.comment_scan_errors == 1
    assert summary.missing_token_findings_by_source == {
        "comment_scan_error": 1,
        "none": 2,
    }
    assert any(
        item["number"] == 7 and item["commentCheckError"] == "issue_comments: throttled"
        for item in missing
    )
    assert any(
        item["number"] == 7
        and "comment_scan_error" in item["details"]["tokenSignalSources"]
        for item in missing
    )

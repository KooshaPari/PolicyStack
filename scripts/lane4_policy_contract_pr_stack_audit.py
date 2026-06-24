#!/usr/bin/env python3
"""Detect stacked open PRs in a repository that are missing approval-token markers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


DEFAULT_APPROVAL_TOKEN_LABEL = "approval-token"
DEFAULT_APPROVAL_TOKEN_PATTERNS = (
    r"/stack-approve\b",
    r"@stack-approve\b",
    r"/stack-merge\b",
    r"/policy-stack-approve\b",
    r"approval token",
    r"approval-token",
    r"approval_token",
    r"stack-ok\b",
    r"stack-ready\b",
    r"approve-stack\b",
    r"merge-stack\b",
    r"stack-approve\b",
)
STACK_TARGET_BRANCHES = {"main", "master"}


@dataclass(frozen=True)
class FindingsSummary:
    repo: str
    scanned_prs: int
    stacked_prs: int
    missing_token_count: int
    comment_scan_errors: int
    missing_token_findings_by_source: dict[str, int]


def run_gh(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        default="KooshaPari/policy-contract",
        help="Repository to inspect in OWNER/REPO form.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of open PRs to inspect.",
    )
    parser.add_argument(
        "--approval-token-label",
        default=DEFAULT_APPROVAL_TOKEN_LABEL,
        help="Label name that indicates an approval token was explicitly provided.",
    )
    parser.add_argument(
        "--approval-token-pattern",
        action="append",
        default=list(DEFAULT_APPROVAL_TOKEN_PATTERNS),
        help="Regex marker pattern for approval token in title/body/comments.",
    )
    parser.add_argument(
        "--check-comments",
        action="store_true",
        default=True,
        help="Check PR comments for approval markers (default: on).",
    )
    parser.add_argument(
        "--skip-comments",
        action="store_false",
        dest="check_comments",
        help="Skip PR comment checks while preserving title/body checks.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Comment missing-token findings on PRs (no mutation in dry-run mode).",
    )
    parser.add_argument(
        "--comment-template",
        default=(
            "[policy-contract lane4] Stacked PR Audit: this PR appears to be part of a stack "
            "and requires an explicit approval-token marker. To approve the stack, add "
            "the 'approval-token' label or a comment like '/stack-approve' or 'stack-ok'. "
            "Documentation-only PRs are exempt."
        ),
        help="Comment text used only with --apply.",
    )
    parser.add_argument(
        "--pretty-json",
        action="store_true",
        help="Pretty print JSON output.",
    )
    return parser.parse_args()


def _is_stacked_source(branch_name: str) -> bool:
    return branch_name.startswith("stack/")


def _is_stacked_target(branch_name: str) -> bool:
    return branch_name in STACK_TARGET_BRANCHES or branch_name.startswith("stack/")


def _looks_like_stacked(
    pr: dict[str, Any], head_to_pr: dict[str, dict[str, Any]]
) -> bool:
    source = pr.get("headRefName")
    target = pr.get("baseRefName")
    if not isinstance(source, str) or not isinstance(target, str):
        return False

    is_stacked_pair = _is_stacked_source(source) and _is_stacked_target(target)
    parent = head_to_pr.get(target)
    is_stacked_chain = (
        isinstance(parent, dict)
        and _is_stacked_source(source)
        and _is_stacked_source(str(parent.get("headRefName", "")))
    )
    return is_stacked_pair or is_stacked_chain


def list_open_prs(
    repo: str, limit: int
) -> tuple[bool, list[dict[str, Any]] | None, str | None]:
    fields = "number,title,headRefName,baseRefName,state,isDraft,labels,body,url"
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "open",
        "--limit",
        str(limit),
        "--json",
        fields,
    ]
    rc, out, err = run_gh(cmd)
    if rc != 0:
        return False, None, err or "gh pr list command failed"
    try:
        payload = json.loads(out)
        if not isinstance(payload, list):
            return False, None, "gh API returned non-list payload"
        return True, payload, None
    except json.JSONDecodeError as exc:
        return False, None, f"failed to decode gh output: {exc}"


def list_pr_comments(
    repo: str,
    pr_number: int,
) -> tuple[bool, list[dict[str, Any]] | None, str | None]:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/{pr_number}/comments",
        "--paginate",
    ]
    rc, out, err = run_gh(cmd)
    if rc != 0:
        return False, None, err or "gh api issue comments command failed"
    try:
        payload = json.loads(out)
        if not isinstance(payload, list):
            return False, None, "gh api returned non-list payload for comments"
        return True, payload, None
    except json.JSONDecodeError as exc:
        return False, None, f"failed to decode gh comment output: {exc}"


def list_pr_review_comments(
    repo: str,
    pr_number: int,
) -> tuple[bool, list[dict[str, Any]] | None, str | None]:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/pulls/{pr_number}/comments",
        "--paginate",
    ]
    rc, out, err = run_gh(cmd)
    if rc != 0:
        return False, None, err or "gh api review comments command failed"
    try:
        payload = json.loads(out)
        if not isinstance(payload, list):
            return False, None, "gh api returned non-list payload for review comments"
        return True, payload, None
    except json.JSONDecodeError as exc:
        return False, None, f"failed to decode gh review comment output: {exc}"


def list_pr_reviews(
    repo: str,
    pr_number: int,
) -> tuple[bool, list[dict[str, Any]] | None, str | None]:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/pulls/{pr_number}/reviews",
        "--paginate",
    ]
    rc, out, err = run_gh(cmd)
    if rc != 0:
        return False, None, err or "gh api reviews command failed"
    try:
        payload = json.loads(out)
        if not isinstance(payload, list):
            return False, None, "gh api returned non-list payload for reviews"
        return True, payload, None
    except json.JSONDecodeError as exc:
        return False, None, f"failed to decode gh reviews output: {exc}"


def list_pr_comments_all(
    repo: str,
    pr_number: int,
) -> tuple[bool, list[dict[str, Any]] | None, str | None]:
    ok_issue, issue_comments, issue_err = list_pr_comments(repo, pr_number)
    ok_review, review_comments, review_err = list_pr_review_comments(repo, pr_number)
    ok_reviews, reviews, reviews_err = list_pr_reviews(repo, pr_number)

    if not ok_issue and not ok_review:
        if ok_reviews:
            # Continue with review bodies only.
            pass
        else:
            return False, None, issue_err or review_err

    # Surface partial API failures so remediation can avoid acting on incomplete scans.
    errors: list[str] = []
    if not ok_issue and issue_err:
        errors.append(f"issue_comments: {issue_err}")
    if not ok_review and review_err:
        errors.append(f"review_comments: {review_err}")
    if not ok_reviews and reviews_err:
        errors.append(f"reviews: {reviews_err}")
    partial_error = "; ".join(errors) if errors else None

    merged: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for comment in (issue_comments or []) + (review_comments or []) + (reviews or []):
        if not isinstance(comment, dict):
            continue
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or comment_id in seen_ids:
            continue
        seen_ids.add(comment_id)
        merged.append(comment)

    return True, merged, partial_error


def _classify_missing_token_sources(
    signal_sources: list[str],
    comment_error: str | None,
) -> set[str]:
    sources: set[str] = set()
    for signal in signal_sources:
        if signal.startswith("label:"):
            sources.add("label")
        elif signal.startswith("title:"):
            sources.add("title")
        elif signal.startswith("body:"):
            sources.add("body")
        elif signal.startswith("comment["):
            sources.add("comments")
        elif signal.strip():
            sources.add("unknown")
    if not sources and not comment_error:
        sources.add("none")
    if comment_error:
        sources.add("comment_scan_error")
    return sources


def _is_low_risk_pr(repo: str, pr_number: int) -> bool:
    """Check if the PR is considered low risk (e.g., docs only)."""
    cmd = ["gh", "pr", "diff", str(pr_number), "--repo", repo, "--name-only"]
    rc, out, _ = run_gh(cmd)
    if rc != 0 or not out:
        return False

    files = out.splitlines()
    if not files:
        return False

    # Define low-risk patterns (docs, markdown, etc.)
    low_risk_patterns = [
        re.compile(r".*\.md$"),
        re.compile(r"^docs/.*"),
        re.compile(r"^LICENSE$"),
        re.compile(r"^\.github/.*\.md$"),
    ]

    for file in files:
        if not any(pattern.match(file) for pattern in low_risk_patterns):
            return False

    return True


def has_approval_token(
    pr: dict[str, Any],
    repo: str,
    label_name: str,
    patterns: list[str],
    *,
    check_comments: bool,
) -> tuple[bool, list[str], list[str], str | None]:
    found: list[str] = []
    signals: list[str] = []
    compiled_patterns = [(re.compile(pat, re.IGNORECASE), pat) for pat in patterns]

    for label in pr.get("labels", []) or []:
        name = str(label.get("name", "")).strip().lower()
        if name == label_name.lower():
            signal = f"label:{label_name}"
            signals.append(signal)
            found.append(signal)

    searchable = f"{pr.get('title', '')} {pr.get('body', '')}"
    for pattern, raw_pattern in compiled_patterns:
        if pattern.search(searchable):
            signal = f"body:{raw_pattern}"
            found.append(signal)
            signals.append(signal)

    if found:
        return True, sorted(set(found)), sorted(set(signals)), None

    number = pr.get("number")
    if number is not None:
        if _is_low_risk_pr(repo, int(number)):
            signal = "low-risk-exemption:docs-only"
            found.append(signal)
            signals.append(signal)
            return True, sorted(set(found)), sorted(set(signals)), None

    if check_comments:
        number = pr.get("number")
        if number is not None:
            ok, comments, err = list_pr_comments_all(repo, int(number))
            if not ok:
                return False, sorted(set(found)), sorted(set(signals)), err
            for idx, comment in enumerate(comments or []):
                comment_text = str(comment.get("body", ""))
                author = (comment.get("user") or {}).get("login")
                # Skip comments from common bots or if it looks like our own template
                if author and "[bot]" in author:
                    continue
                # Simple check for our signature (lane4_policy_contract_pr_stack_audit)
                if "[policy-contract lane4]" in comment_text:
                    continue

                for pattern, raw_pattern in compiled_patterns:
                    if not pattern.search(comment_text):
                        continue
                    signal = f"comment[{idx}]:{raw_pattern}"
                    found.append(signal)
                    signals.append(signal)

            return bool(found), sorted(set(found)), sorted(set(signals)), None

    return False, sorted(set(found)), sorted(set(signals)), None


def find_stacked_and_token_findings(
    prs: list[dict[str, Any]],
    repo: str,
    label_name: str,
    token_patterns: list[str],
    *,
    check_comments: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], FindingsSummary]:
    head_to_pr: dict[str, dict[str, Any]] = {
        pr["headRefName"]: pr for pr in prs if isinstance(pr.get("headRefName"), str)
    }

    stacked_records: list[dict[str, Any]] = []
    missing_records: list[dict[str, Any]] = []
    comment_scan_errors = 0
    missing_sources = Counter()

    for pr in prs:
        if not _looks_like_stacked(pr, head_to_pr):
            continue

        source = pr.get("headRefName")
        target = pr.get("baseRefName")

        has_token, matches, signals, comment_error = has_approval_token(
            pr,
            repo,
            label_name,
            token_patterns,
            check_comments=check_comments,
        )
        if comment_error:
            comment_scan_errors += 1

        source_is_stacked = bool(
            _is_stacked_source(str(source)) if isinstance(source, str) else False
        )
        target_is_stacked = bool(
            _is_stacked_target(str(target)) if isinstance(target, str) else False
        )
        source = str(source)
        target = str(target)

        record = {
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "source": source,
            "target": target,
            "status": pr.get("state", ""),
            "isDraft": bool(pr.get("isDraft", False)),
            "url": pr.get("url", ""),
            "hasApprovalToken": has_token,
            "isStackSource": source_is_stacked,
            "isStackTarget": target_is_stacked,
            "isStackChain": (
                target in head_to_pr
                and _is_stacked_source(
                    str((head_to_pr.get(target) or {}).get("headRefName", ""))
                )
            ),
            "commentCheckError": comment_error,
            "approvalTokenSignals": matches,
            "approvalTokenSignalSources": sorted(set(signals)),
            "missingApprovalToken": not has_token,
        }

        stacked_records.append(record)

        if not has_token:
            missing_token_signal_sources = _classify_missing_token_sources(
                sorted(set(signals)),
                comment_error,
            )
            for source in sorted(missing_token_signal_sources):
                missing_sources[source] += 1
            missing_records.append(
                {
                    **record,
                    "finding": "missing_approval_token",
                    "details": {
                        "expected": (
                            "label 'approval-token' or marker in title/body/comments"
                        ),
                        "candidates": token_patterns,
                        "commentCheckError": comment_error,
                        "tokenSignals": sorted(set(signals)),
                        "tokenSignalSources": sorted(missing_token_signal_sources),
                    },
                }
            )

    stacked_records = sorted(
        stacked_records,
        key=lambda item: (
            int(item.get("number", 0)) if isinstance(item.get("number"), int) else 0,
            str(item.get("source", "")),
            str(item.get("target", "")),
        ),
    )
    missing_records = sorted(
        missing_records,
        key=lambda item: (
            int(item.get("number", 0)) if isinstance(item.get("number"), int) else 0,
            str(item.get("source", "")),
            str(item.get("target", "")),
        ),
    )

    return (
        stacked_records,
        missing_records,
        FindingsSummary(
            repo=repo,
            scanned_prs=len(prs),
            stacked_prs=len(stacked_records),
            missing_token_count=len(missing_records),
            comment_scan_errors=comment_scan_errors,
            missing_token_findings_by_source=dict(missing_sources),
        ),
    )


def apply_remediation(
    repo: str, findings: list[dict[str, Any]], comment_template: str
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    comment_signature = comment_template[:180]
    for item in findings:
        number = str(item.get("number", ""))
        if not number:
            continue
        if item.get("commentCheckError"):
            actions.append(
                {
                    "number": item.get("number"),
                    "applied": False,
                    "action": "commented",
                    "reason": "skip_due_to_comment_scan_error",
                }
            )
            continue

        ok, comments, err = list_pr_comments_all(repo, int(number))
        if not ok:
            actions.append(
                {
                    "number": item.get("number"),
                    "applied": False,
                    "action": "commented",
                    "error": f"unable to verify prior comments: {err}",
                }
            )
            continue

        for comment in comments or []:
            if comment_signature and comment_signature in str(comment.get("body", "")):
                actions.append(
                    {
                        "number": item.get("number"),
                        "applied": False,
                        "action": "commented",
                        "reason": "already_remediated",
                    }
                )
                break
        else:
            cmd = [
                "gh",
                "pr",
                "comment",
                number,
                "--repo",
                repo,
                "--body",
                comment_template,
            ]
            rc, _, err = run_gh(cmd)
            if rc == 0:
                actions.append(
                    {
                        "number": item.get("number"),
                        "applied": True,
                        "action": "commented",
                    }
                )
            else:
                actions.append(
                    {
                        "number": item.get("number"),
                        "applied": False,
                        "action": "commented",
                        "error": err or "unknown gh error",
                    }
                )
    return actions


def main() -> int:
    args = parse_args()
    ok, prs, error = list_open_prs(args.repo, args.limit)

    if not ok:
        print(json.dumps({"ok": False, "error": error}))
        return 1

    stacked_records, missing_records, summary = find_stacked_and_token_findings(
        prs,
        args.repo,
        args.approval_token_label,
        args.approval_token_pattern,
        check_comments=args.check_comments,
    )

    actions: list[dict[str, Any]] = []
    if args.apply and missing_records:
        actions = apply_remediation(args.repo, missing_records, args.comment_template)

    result_summary = {
        "repo": summary.repo,
        "generatedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scannedOpenPrs": summary.scanned_prs,
        "stackedCandidates": summary.stacked_prs,
        "missingTokenFindings": summary.missing_token_count,
        "commentScanErrors": summary.comment_scan_errors,
        "missingTokenFindingsBySource": summary.missing_token_findings_by_source,
        "commentScanEnabled": bool(args.check_comments),
        "applyMode": bool(args.apply),
    }

    result = {
        "ok": True,
        "summary": result_summary,
        "stackedPrs": stacked_records,
        "missingTokenFindings": missing_records,
        "actions": actions,
    }

    print(json.dumps(result, indent=2 if args.pretty_json else None, sort_keys=True))

    if summary.comment_scan_errors:
        return 2
    if args.apply:
        failed_actions = [a for a in actions if not a.get("applied", False)]
        if missing_records and any(
            item.get("commentCheckError") for item in missing_records
        ):
            return 2
        if failed_actions:
            return 3
        return 0
    if summary.missing_token_count:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

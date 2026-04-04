"""Runtime sidecar and audit artifact helpers."""
from __future__ import annotations

import datetime
import json
import re
import sys
import uuid
from pathlib import Path


def build_run_sidecar(
    *,
    harness: str,
    task_domain: str,
    task_instance: str | None,
    policy_hash: str,
    scope_chain: list[str],
    source_files: list[str] | None = None,
    policy_payload_ref: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Build a run sidecar payload matching the repo contract."""
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "policy_hash": policy_hash,
        "scope_chain": scope_chain,
        "audit": {},
        "extensions": {},
        "resolved_at": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "harness": harness,
        "task_domain": task_domain,
        "task_instance": task_instance,
        "source_files": source_files or [],
        "policy_payload_ref": policy_payload_ref,
    }


def append_audit_event(
    *,
    audit_log_path: Path,
    event: dict,
) -> None:
    """Append one JSONL audit event."""
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def build_permission_audit_event(
    *,
    source: str,
    request: dict,
    result: dict,
    context: dict | None = None,
    conversation: dict | None = None,
) -> dict:
    """Build a structured permission audit event."""
    event = {
        "event_type": "permission_decision",
        "source": source,
        "timestamp": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "request": request,
        "result": result,
    }
    if context:
        event["context"] = context
    if conversation:
        event["conversation"] = conversation
    return event


def _compact_text(value: object, *, limit: int = 160) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def format_permission_audit_summary(event: dict) -> str:
    """Format a one-line human summary for an audit event."""
    request = event.get("request") or {}
    result = event.get("result") or {}
    context = event.get("context") or {}
    conversation = event.get("conversation") or {}
    command = request.get("raw_command") or request.get("command") or ""
    parts = [
        "permission_decision",
        f"source={event.get('source', 'unknown')}",
        f"decision={result.get('final_decision', 'unknown')}",
        f"policy={result.get('policy_decision', 'unknown')}",
        f"action={request.get('action', 'unknown')}",
    ]
    if context.get("repo"):
        parts.append(f"repo={_compact_text(context['repo'], limit=48)}")
    if context.get("task_domain"):
        parts.append(f"task_domain={_compact_text(context['task_domain'], limit=48)}")
    if conversation.get("session_id"):
        parts.append(f"session={_compact_text(conversation['session_id'], limit=48)}")
    if conversation.get("tool_name"):
        parts.append(f"tool={_compact_text(conversation['tool_name'], limit=48)}")
    if request.get("cwd"):
        parts.append(f"cwd={_compact_text(request['cwd'], limit=72)}")
    if command:
        parts.append(f"command={_compact_text(command)}")
    rule = (result.get("evaluation") or {}).get("winning_rule") or {}
    if rule.get("id"):
        parts.append(f"rule={_compact_text(rule['id'], limit=72)}")
    return " ".join(parts)


def record_audit_event(
    *,
    audit_log_path: Path | None,
    event: dict,
    stream: str | None = None,
) -> None:
    """Append an audit event to file and/or emit it to a stream."""
    if audit_log_path is not None:
        append_audit_event(audit_log_path=audit_log_path, event=event)
    if stream == "stderr":
        stream_handle = sys.stderr
    elif stream == "stdout":
        stream_handle = sys.stdout
    else:
        stream_handle = None
    if stream_handle is not None:
        stream_handle.write(format_permission_audit_summary(event) + "\n")
        stream_handle.write(json.dumps(event, sort_keys=True) + "\n")
        stream_handle.flush()


def write_sidecar(
    *,
    sidecar_path: Path,
    payload: dict,
) -> None:
    """Write a session sidecar JSON artifact."""
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_audit_log(audit_log_path: Path) -> list[dict]:
    """Read all events from a JSONL audit log file."""
    events = []
    if not audit_log_path.exists():
        return events
    with audit_log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def verify_audit_chain(events: list[dict]) -> dict:
    """Verify the integrity of an audit event chain.

    Returns a dict with:
        - valid: bool indicating if chain is valid
        - message: descriptive message
        - events_checked: number of events validated
    """
    if not events:
        return {
            "valid": True,
            "message": "No events to verify",
            "events_checked": 0,
        }

    # Basic validation: check all events have required fields
    required_fields = {"run_id", "action", "final_decision"}
    invalid_events = []

    for i, event in enumerate(events):
        missing = required_fields - set(event.keys())
        if missing:
            invalid_events.append((i, event, missing))

    if invalid_events:
        return {
            "valid": False,
            "message": f"Found {len(invalid_events)} event(s) with missing required fields",
            "invalid_events": [
                {
                    "index": idx,
                    "event": evt,
                    "missing_fields": list(missing),
                }
                for idx, evt, missing in invalid_events
            ],
            "events_checked": len(events),
        }

    return {
        "valid": True,
        "message": f"All {len(events)} event(s) are valid",
        "events_checked": len(events),
    }


def filter_audit_events(
    events: list[dict],
    *,
    since: datetime.datetime | None = None,
    until: datetime.datetime | None = None,
    action: str | None = None,
    decision: str | None = None,
    actor_pattern: str | None = None,
) -> list[dict]:
    """Filter audit events by criteria."""
    filtered = events

    if action:
        filtered = [e for e in filtered if e.get("action") == action]

    if decision:
        filtered = [e for e in filtered if e.get("final_decision") == decision]

    if since or until:
        filtered_time = []
        for e in filtered:
            # Try to parse timestamp from event; assume ISO format if present
            event_ts_str = e.get("timestamp")
            if not event_ts_str:
                filtered_time.append(e)
                continue

            try:
                # Handle both 'Z' and '+00:00' formats
                ts_str = event_ts_str.replace("Z", "+00:00")
                event_ts = datetime.datetime.fromisoformat(ts_str)

                if since and event_ts < since:
                    continue
                if until and event_ts > until:
                    continue
                filtered_time.append(e)
            except (ValueError, AttributeError):
                # If we can't parse, include the event
                filtered_time.append(e)

        filtered = filtered_time

    if actor_pattern:
        try:
            pattern = re.compile(actor_pattern)
            filtered = [
                e for e in filtered
                if e.get("actor") and pattern.search(e.get("actor", ""))
            ]
        except re.error:
            # If pattern is invalid, just do string matching
            filtered = [
                e for e in filtered
                if e.get("actor") and actor_pattern in e.get("actor", "")
            ]

    return filtered

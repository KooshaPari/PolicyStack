# Known Issues and Checklist Notes

## Host Apply Order and Merge-Safety Checklist

Use this before each host sync operation.

1. Build policy payload.
- Generate resolved policy JSON first.
- Verify conditional split counts in emitted summary.

2. Emit host artifacts to temporary directory.
- Run sync with explicit target directory.
- Verify output files exist and wrapper manifest points at the emitted bundle.

3. Merge-safe apply order.
- Apply codex rules first, preserving append-only semantics in the managed marker block.
- Apply Cursor config next, preserving existing `permissions.allow/deny` lists.
- Apply Claude permissions next, preserving existing `allow/deny/ask` values.
- Apply Droid settings last.
- Re-read each file after each step when troubleshooting conflicts.

4. Idempotence checks.
- Re-apply the same artifacts and ensure only managed additions grow lists once.
- Confirm no duplicate entries are introduced by the merge operation.

5. Fallback behavior.
- If `policy-wrapper-dispatch.sh --require-binary` is set, treat a missing or unhealthy binary as a hard failure.
- Otherwise ensure the fallback reason is deterministic from fallback metadata in the dispatch output.

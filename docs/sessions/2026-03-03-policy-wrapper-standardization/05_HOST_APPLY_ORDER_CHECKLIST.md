# Host Apply Order and Merge-Safety Checklist

Use this before each host sync operation.

1) Build policy payload
- Generate resolved policy JSON first.
- Verify conditional split counts in emitted summary.

2) Emit host artifacts to temporary directory
- Run sync with explicit target directory.
- Verify output files exist and wrapper manifest points at the emitted bundle.

3) Merge-safe apply order
- Apply codex rules first (append-only semantics in managed marker block).
- Apply Cursor config next (existing `permissions.allow/deny` lists preserved).
- Apply Claude permissions next (existing `allow/deny/ask` preserved).
- Apply Droid settings last.
- Re-read each file after each step when troubleshooting conflicts.

4) Idempotence checks
- Re-apply same artifacts and ensure only managed additions grow lists once.
- Confirm no duplicate entries introduced by merge operation.

5) Fallback behavior
- If `policy-wrapper-dispatch.sh --require-binary` is set, treat missing/unhealthy binary as hard failure.
- Otherwise ensure deterministic fallback reason from fallback metadata in dispatch output.

# Known Issues

## Pre-existing

- `PolicyStack-wtrees/sladge-current` is behind canonical and has unrelated local `wrappers/go/main.go` changes.
- The documented uv-based validation form may be blocked by sandbox cache permissions.
- Canonical `ci/add-mypy` advanced by one wrapper commit while this refresh was in progress; the isolated worktree was fast-forwarded before validation and commit.

## Session Blockers

- No blocking validation failures.

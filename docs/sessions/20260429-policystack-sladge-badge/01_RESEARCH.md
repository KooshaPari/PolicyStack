# Research

## Repo Fit

PolicyStack is in scope for the sladge rollout because it defines policy scope
for multi-harness AgentOps, including Codex, Cursor-agent, Claude, and
Factory-Droid.

## Local State

Canonical `PolicyStack` had unrelated local edits in `CLAUDE.md`, `PRD.md`, and
`TEST_COVERAGE_MATRIX.md`. The badge change was prepared in an isolated
worktree to avoid mixing those changes.

## Decision

Treat this as a documentation/governance badge update only. Do not modify policy
contract behavior, generated snapshots, or runtime wrapper code.

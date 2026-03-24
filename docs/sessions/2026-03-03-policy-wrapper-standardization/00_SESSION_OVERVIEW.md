# Policy Wrapper Standardization Session Overview

## Session objective
Establish a unified policy authorization pipeline where host tools (Cursor/Claude/Codex/Droid) handle static command gates and wrapper runtimes enforce conditional policy checks.

## Current status
- Policy parser now emits conditional/unconditional split data for host export.
- Conditional host export tests validate non-mutation and additive behavior for allow/request/deny.
- Dispatch/runtime path now supports optional binary health checks and clearer required-binary error output.

## Completed acceptance checkpoints
- Unconditional host command surfaces remain stable when conditional export is enabled.
- Conditional `allow` and `request` commands are represented in host surfaces without regressing static deny/ask lists.
- Conditional `allow`/`request`/`deny` permutations now have explicit parity assertions across Cursor, Claude, Codex, and Droid outputs.
- Manual fallback behavior remains deterministic when wrapper binaries are unavailable.
- Dispatch smoke-test specification and cross-project sync note are published in session artifacts.
- Stacked-PR governance audit now gates workflow transitions from explicit lane4 exit codes.
- Stack-audit deterministic output/order and remediation failure mode have test coverage.
- Smoke host-hook script now validates both allow and blocked dispatch outcomes in one execution.

## Open risks
- Wrapper runtime parity across Go/Rust/Zig still needs full golden parity coverage.
- Dispatch candidate health check is optional and currently validates with `--help` semantics.

## Active execution plan (stacked-PR governance wave)
- Worklane 1: `lane4` stacked-PR script parity (workflow + open PR scan + comment token checks) — done.
- Worklane 2: verify open stacked PR findings are actionable (label/comment tokens) and monitor any remaining blockers.
- Worklane 3: align token set/docs with policy stack-review conventions and shared governance docs.
- Worklane 4: run workflow-policy test coverage if/when CI/network allows validation — done.

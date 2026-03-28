# Specifications

## Objective

Standardize the policy wrapper pipeline while preserving deterministic host export behavior.

## Acceptance Criteria

- Conditional host export remains additive for allow/request/deny categories.
- Wrapper runtime behavior stays consistent across policy gating paths.
- Session artifacts capture the policy pipeline state cleanly for later resume.


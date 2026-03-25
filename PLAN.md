# Plan - policy-contract

## Phase 1: Core Resolution (Complete)

| Task | Description | Status |
|------|-------------|--------|
| P1.1 | 6-level scope resolver | Done |
| P1.2 | Extension precedence and dedup | Done |
| P1.3 | CLI interface (resolve.py) | Done |

## Phase 2: Conditional Rules (Complete)

| Task | Description | Depends On | Status |
|------|-------------|------------|--------|
| P2.1 | Nested all/any condition groups | P1.1 | Done |
| P2.2 | Host artifact generation | P2.1 | Done |
| P2.3 | Wrapper payload for Go/Rust/Zig evaluators | P2.2 | Done |

## Phase 3: Governance (Complete)

| Task | Description | Depends On | Status |
|------|-------------|------------|--------|
| P3.1 | Schema validation script | P1.1 | Done |
| P3.2 | Snapshot drift detection | P1.1 | Done |
| P3.3 | Version governance | P1.1 | Done |
| P3.4 | Pytest governance suite | P3.1-P3.3 | Done |

## Phase 4: Cross-Language Evaluators (In Progress)

| Task | Description | Depends On | Status |
|------|-------------|------------|--------|
| P4.1 | Go wrapper evaluator | P2.3 | Done |
| P4.2 | Rust wrapper evaluator | P2.3 | Done |
| P4.3 | Zig wrapper evaluator | P2.3 | Done |

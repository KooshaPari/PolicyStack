# Code Entity Map - policy-contract

## Forward Map (Code -> Requirements)

| Entity | File | FR |
|--------|------|----|
| `resolve.py` | `resolve.py` | FR-RES-001, FR-RES-002, FR-RES-003, FR-RES-004 |
| `policy_lib.py` | `policy_lib.py` | FR-COND-001, FR-COND-002, FR-COND-003 |
| `sync_host_rules.py` | `scripts/sync_host_rules.py` | FR-HOST-001 |
| `policy_wrapper.schema.json` | `agent-scope/policy_wrapper.schema.json` | FR-HOST-002 |
| `validate_policy_contract.py` | `scripts/validate_policy_contract.py` | FR-GOV-001 |
| `generate_policy_snapshot.py` | `scripts/generate_policy_snapshot.py` | FR-GOV-002 |
| `check_policy_versions.py` | `scripts/check_policy_versions.py` | FR-GOV-003 |
| Go evaluator | `wrappers/go/` | FR-COND-001, FR-HOST-002 |
| Rust evaluator | `wrappers/rust/` | FR-COND-001, FR-HOST-002 |
| Zig evaluator | `wrappers/zig/` | FR-COND-001, FR-HOST-002 |

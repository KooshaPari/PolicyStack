# Comparison Matrix

## Feature Comparison

This document compares **policy-contract** with similar tools in the policy scope, authorization, and multi-harness governance space.

| Repository | Purpose | Key Features | Language/Framework | Maturity | Comparison |
|------------|---------|--------------|-------------------|----------|------------|
| **policy-contract (this repo)** | Policy scope stack | 6-scope hierarchy, Multi-harness, Conditional rules, Host sync | Python | Stable | AgentOps governance |
| [OPA](https://github.com/open-policy-agent/opa) | Policy engine | Rego language, Cloud-native | Go | Stable | Enterprise policy |
| [Sentinel](https://github.com/hashicorp/sentinel) | Policy framework | DSL, Terraform integration | Go | Stable | HashiCorp ecosystem |
| [AWS IAM](https://github.com/awsdocs) | Access control | Policies, Roles, JSON | Various | Stable | Cloud access control |
| [Casbin](https://github.com/casbin/casbin) | Access control | Models, Adapters | Go | Stable | General AC library |
| [Open Policy Agent](https://github.com/open-policy-agent/opa) | Policy engine | Rego, REST API | Go | Stable | CNCF project |

## Detailed Feature Comparison

### Policy Scope Hierarchy

| Scope | policy-contract | OPA | AWS IAM | Casbin |
|-------|----------------|-----|---------|--------|
| system (global) | ✅ | ✅ | ✅ | ✅ |
| user (operator) | ✅ | ✅ | ✅ | ✅ |
| repo (baseline) | ✅ | ✅ | ❌ | ✅ |
| harness (agent) | ✅ | ❌ | ❌ | ❌ |
| task_domain | ✅ | ❌ | ❌ | ❌ |
| task_instance | ✅ | ✅ | ❌ | ✅ |

### Multi-Harness Support

| Feature | policy-contract | OPA | Sentinel |
|---------|----------------|-----|---------|
| Codex | ✅ | ❌ | ❌ |
| Claude | ✅ | ❌ | ❌ |
| Cursor | ✅ | ❌ | ❌ |
| Factory-Droid | ✅ | ❌ | ❌ |
| Generic agent | ❌ | ✅ | ✅ |

### Conditional Rules

| Feature | policy-contract | OPA | Sentinel |
|---------|----------------|-----|---------|
| Rule conditions | ✅ (all/any) | ✅ (Rego) | ✅ |
| Git predicates | ✅ | ❌ | ❌ |
| Host-specific output | ✅ | ❌ | ❌ |
| Wrapper evaluators | ✅ (Go/Rust/Zig) | ❌ | ❌ |

### Host Integration

| Feature | policy-contract | OPA | Sentinel |
|---------|----------------|-----|---------|
| Codex rules | ✅ | ❌ | ❌ |
| Cursor rules | ✅ | ❌ | ❌ |
| Claude rules | ✅ | ❌ | ❌ |
| Factory-Droid rules | ✅ | ❌ | ❌ |
| REST API | ❌ | ✅ | ✅ |

## Unique Value Proposition

policy-contract provides:

1. **6-Scope Hierarchy**: From system-wide to per-task-instance policy layers
2. **Multi-Harness**: Policy enforcement for Codex, Claude, Cursor, Factory-Droid
3. **Conditional Rules**: Git predicates (worktree, clean, synced) for safety
4. **Host Sync**: Generate host-specific policy fragments automatically

## Policy Discovery Precedence

1. Extension precedence: `.yaml` > `.yml` > `.json`
2. Default scope: `system` → `user` → `repo`
3. Discovery scope: `harness` → `task-domain` → `task-instance`

## References

- OPA: [open-policy-agent/opa](https://github.com/open-policy-agent/opa)
- Sentinel: [hashicorp/sentinel](https://github.com/hashicorp/sentinel)
- Casbin: [casbin/casbin](https://github.com/casbin/casbin)
- AWS IAM: [awsdocs](https://github.com/awsdocs)

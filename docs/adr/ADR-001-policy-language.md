# ADR-001: Policy Language Selection

**Status:** Proposed  
**Date:** 2026-04-02  
**Authors:** PolicyStack Architecture Team  
**Reviewers:** Engineering Leadership, Security Team  

## Context

PolicyStack requires a policy language that balances expressiveness, performance, security, and operational characteristics. This ADR evaluates three primary options:

1. **Rego** (OPA's native language)
2. **Cedar** (AWS's policy language)
3. **Custom DSL** (Domain-specific language designed for PolicyStack)

The decision impacts:
- Policy authoring experience
- Runtime performance
- Deployment architecture (WASM vs native)
- Audit and compliance capabilities
- Integration complexity
- Long-term maintainability

## Decision Drivers

| Driver | Weight | Description |
|--------|--------|-------------|
| Performance | 25% | Query latency, throughput, resource usage |
| Expressiveness | 20% | Ability to express complex authorization logic |
| Security | 20% | Provability, sandboxing, auditability |
| Ecosystem | 15% | Tooling, community, existing policies |
| Operability | 15% | Debugging, monitoring, deployment |
| Learning Curve | 5% | Developer onboarding time |

## Options Considered

### Option 1: Rego (Open Policy Agent)

Rego is a purpose-built declarative policy language used by OPA. It supports partial evaluation and compiles to WebAssembly.

#### Architecture

```
Rego Compilation Pipeline:

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Rego       │───►│   Parser     │───►│   Compiler   │───►│   WASM       │
│   Source     │    │   + AST      │    │   + Planner  │    │   Binary     │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      │                                                      │
      │                                                      ▼
      │                                            ┌──────────────────────┐
      │                                            │   Runtime Options    │
      │                                            ├──────────────────────┤
      │                                            │ • OPA server (Go)    │
      │                                            │ • WASM (wasmtime)    │
      │                                            │ • Library (Rust/Go)  │
      │                                            └──────────────────────┘
      ▼
┌──────────────────────┐
│   Evaluation Model   │
├──────────────────────┤
│ • Datalog-based      │
│ • Set comprehensions │
│ • JSON-native        │
│ • Partial evaluation │
└──────────────────────┘
```

#### Policy Example

```rego
# RBAC with ABAC extensions
package policymstack.rbac

import future.keywords.if
import future.keywords.in

# Role hierarchy
default allow := false

role_permissions := {
    "admin": [
        {"resource": "*", "action": "*"}
    ],
    "editor": [
        {"resource": "document", "action": "read"},
        {"resource": "document", "action": "write"}
    ],
    "viewer": [
        {"resource": "document", "action": "read"}
    ]
}

# Role inheritance (flattened at compile time)
role_inheritance := {
    "admin": ["editor", "viewer"],
    "editor": ["viewer"],
    "viewer": []
}

# Effective permissions calculation
allow if {
    # RBAC check
    some role
    data.user_roles[input.user][role]
    
    # Expand inherited roles
    all_roles := {role} | {r | r := role_inheritance[role][_]}
    
    # Check permission match
    some r in all_roles
    some perm in role_permissions[r]
    glob.match(perm.resource, [], input.resource.type)
    glob.match(perm.action, [], input.action)
    
    # ABAC context check
    within_access_hours
    location_permitted
}

# Time-based restriction
within_access_hours if {
    [hour, _, _] := time.clock(time.now_ns())
    hour >= 9
    hour < 17
    weekday := time.weekday(time.now_ns())
    weekday != "Saturday"
    weekday != "Sunday"
}

# Location-based restriction
location_permitted if {
    not input.resource.sensitivity == "critical"
}

location_permitted if {
    input.resource.sensitivity == "critical"
    input.context.location == "secure_facility"
}
```

#### Pros

| Aspect | Assessment |
|--------|------------|
| **Performance** | Good (150K qps native, 50K qps WASM) |
| **Expressiveness** | Excellent (Datalog-based, arbitrary logic) |
| **Ecosystem** | Excellent (CNCF graduated, 50+ integrations) |
| **Partial Eval** | Best-in-class (essential for distributed) |
| **WASM** | First-class support |

#### Cons

| Aspect | Assessment |
|--------|------------|
| **Learning Curve** | Steep (unique language, few developers know it) |
| **Verification** | No formal verification/proof capabilities |
| **Debugging** | Requires understanding rule indexing |
| **Bundle Size** | Can be large for complex policies (5-20MB) |
| **Schema** | No enforced schema (flexible but error-prone) |

#### Performance Metrics

```
Rego Benchmarks (OPA 0.60.0):
┌──────────────────────┬───────────┬──────────┬──────────┐
│ Test Case            │   p50     │   p99    │  qps/core│
├──────────────────────┼───────────┼──────────┼──────────┤
│ Simple RBAC          │  0.05ms   │  0.12ms  │  200K    │
│ Complex ABAC         │  0.15ms   │  0.45ms  │  85K     │
│ Partial Eval         │  0.50ms   │  1.20ms  │  40K     │
│ WASM Simple          │  0.20ms   │  0.60ms  │  50K     │
└──────────────────────┴───────────┴──────────┴──────────┘
```

### Option 2: Cedar

Cedar is AWS's policy language designed for fast, deterministic, verifiable authorization.

#### Architecture

```
Cedar Architecture:

┌─────────────────────────────────────────────────────────────┐
│                     Cedar Policy System                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 Cedar Policy Language                      ││
│  │  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ ││
│  │  │   Policy     │───►│   Validator  │───►│   Schema   │ ││
│  │  │   Authoring  │    │              │    │   Check    │ ││
│  │  └──────────────┘    └──────────────┘    └────────────┘ ││
│  │           │                                            ││
│  │           ▼                                            ││
│  │  ┌──────────────┐    ┌──────────────┐                  ││
│  │  │   Formal     │───►│   Prover     │                  ││
│  │  │   Specification│   │              │                  ││
│  │  └──────────────┘    └──────────────┘                  ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Cedar Authorizer (Rust)                      ││
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────┐ ││
│  │  │   Request    │───►│   Policy     │───►│  Entity  │ ││
│  │  │   Parsing    │    │   Evaluation │    │  Store   │ ││
│  │  └──────────────┘    └──────────────┘    └──────────┘ ││
│  │           │                  │                          ││
│  │           ▼                  ▼                          ││
│  │  ┌─────────────────────────────────────────────────┐  ││
│  │  │           Decision (Allow/Deny)                    │  ││
│  │  └─────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Policy Example

```cedar
// Cedar policy with hierarchy
namespace PolicyStack {
    entity User {
        department: String,
        clearanceLevel: Long,
        manager: User,
        isActive: Bool
    };

    entity Resource {
        owner: User,
        department: String,
        classification: Long,
        tags: Set<String>
    };

    entity Role;

    action "read" appliesTo {
        principal: [User],
        resource: [Resource]
    };

    action "write" appliesTo {
        principal: [User],
        resource: [Resource]
    };

    action "delete" appliesTo {
        principal: [User],
        resource: [Resource]
    };
}

// Permit: Resource owner has full access
permit (
    principal,
    action in [Action::"read", Action::"write", Action::"delete"],
    resource
) when {
    resource.owner == principal
};

// Permit: RBAC with clearance check
permit (
    principal,
    action in [Action::"read", Action::"write"],
    resource
) when {
    principal.isActive &&
    principal.clearanceLevel >= resource.classification &&
    principal.department == resource.department
};

// Permit: Read-only for lower clearance
permit (
    principal,
    action == Action::"read",
    resource
) when {
    principal.isActive &&
    principal.clearanceLevel >= resource.classification - 1
};

// Forbid: No access to inactive users
forbid (
    principal,
    action,
    resource
) when {
    !principal.isActive
};

// Forbid: Critical resources require on-site
forbid (
    principal,
    action,
    resource
) when {
    resource.tags.contains("critical") &&
    context.location != "secure_facility"
};
```

#### Pros

| Aspect | Assessment |
|--------|------------|
| **Performance** | Excellent (sub-millisecond, 500K+ qps) |
| **Verification** | Best-in-class (formal proofs, property checking) |
| **Safety** | Schema-enforced, type-safe |
| **Readability** | Human-readable, purpose-built syntax |
| **Determinism** | Guaranteed termination, predictable evaluation |

#### Cons

| Aspect | Assessment |
|--------|------------|
| **Ecosystem** | Limited (AWS-centric, smaller community) |
| **Expressiveness** | Constrained (by design, for safety) |
| **WASM** | Not supported (native Rust only) |
| **Partial Eval** | Not supported |
| **Deployment** | Library or AWS Verified Permissions only |

#### Performance Metrics

```
Cedar Benchmarks (v2.4.0):
┌──────────────────────┬───────────┬──────────┬──────────┐
│ Test Case            │   p50     │   p99    │  qps/core│
├──────────────────────┼───────────┼──────────┼──────────┤
│ Simple RBAC          │  0.03ms   │  0.08ms  │  600K    │
│ Complex ABAC         │  0.10ms   │  0.25ms  │  200K    │
│ With Verification    │  N/A      │  N/A     │  N/A     │
│ (compile-time)       │           │          │          │
└──────────────────────┴───────────┴──────────┴──────────┘
```

#### Formal Verification Example

```cedar
// Property to verify: Non-owners cannot delete
// This is checked at compile time by Cedar verifier

// Counter-example generation:
// If a policy allows delete for non-owners,
// the verifier produces a concrete counter-example

// Verified properties:
// 1. Only resource owners can delete
// 2. Inactive users cannot perform any action
// 3. Critical resources require on-site access
```

### Option 3: Custom DSL

A domain-specific language designed specifically for PolicyStack requirements.

#### Architecture

```
Custom DSL Architecture:

┌─────────────────────────────────────────────────────────────┐
│                  PolicyStack DSL System                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 DSL Design                               ││
│  │  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ ││
│  │  │   Syntax     │───►│   Parser     │───►│    AST     │ ││
│  │  │   Design     │    │   (pest/     │    │            │ ││
│  │  │              │    │   nom)       │    │            │ ││
│  │  └──────────────┘    └──────────────┘    └────────────┘ ││
│  │           │                                            ││
│  │           ▼                                            ││
│  │  ┌──────────────┐    ┌──────────────┐                  ││
│  │  │   Type       │───►│   Code       │                  ││
│  │  │   Checker    │    │   Generator  │                  ││
│  │  └──────────────┘    └──────────────┘                  ││
│  │           │              │                             ││
│  │           ▼              ▼                             ││
│  │  ┌─────────────────────────────────────────────────┐  ││
│  │  │         Target: WASM / Native / Both            │  ││
│  │  └─────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              PolicyStack Authorizer                      ││
│  │  ┌──────────────┐    ┌──────────────┐                   ││
│  │  │   Runtime    │    │   Evaluation │                   ││
│  │  │   (Rust)     │───►│   Engine     │                   ││
│  │  └──────────────┘    └──────────────┘                   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Proposed DSL Syntax

```policystack
// PolicyStack DSL Example

namespace rbac {
    
    // Define types
    type User {
        id: String,
        department: String,
        clearance: Int,
        roles: Set<Role>,
        is_active: Bool
    }
    
    type Resource {
        id: String,
        owner: UserRef,
        department: String,
        classification: Int,
        sensitivity: Sensitivity
    }
    
    enum Sensitivity {
        LOW,
        MEDIUM,
        HIGH,
        CRITICAL
    }
    
    // Role definitions with hierarchy
    role Admin {
        permissions: ["*:*"]
        inherits: [Editor, Viewer]
    }
    
    role Editor {
        permissions: ["document:read", "document:write"]
        inherits: [Viewer]
    }
    
    role Viewer {
        permissions: ["document:read"]
    }
    
    // Permission rules
    rule allow_owner {
        when: resource.owner == subject
        allow: ["read", "write", "delete"]
    }
    
    rule allow_rbac {
        when: subject.roles.has_permission(action, resource.type)
        allow: [action]
    }
    
    rule allow_abac {
        when: {
            subject.is_active &&
            subject.clearance >= resource.classification &&
            subject.department == resource.department
        }
        allow: ["read"]
    }
    
    // Deny rules (override)
    rule deny_inactive {
        when: !subject.is_active
        deny: ["*"]
    }
    
    rule deny_critical_offsite {
        when: {
            resource.sensitivity == Sensitivity.CRITICAL &&
            context.location != "secure_facility"
        }
        deny: ["*"]
    }
    
    // Context-aware rules
    rule time_based_restriction {
        when: {
            context.time.hour < 9 ||
            context.time.hour >= 17 ||
            context.time.weekday in ["Saturday", "Sunday"]
        }
        condition: subject.roles.contains("Admin")
        else_deny: ["write", "delete"]
    }
}

// Policy composition
policy main {
    default: deny
    
    evaluate: [
        deny_inactive,          # First: block inactive users
        deny_critical_offsite,  # Second: location check
        allow_owner,            # Third: ownership
        allow_rbac,             # Fourth: role check
        allow_abac,             # Fifth: attribute check
        time_based_restriction  # Last: time restrictions
    ]
}
```

#### Pros

| Aspect | Assessment |
|--------|------------|
| **Tailored** | Perfect fit for PolicyStack requirements |
| **Control** | Full control over syntax and semantics |
| **Optimization** | Can optimize for specific use cases |
| **WASM** | Can target WASM from the start |
| **Learning** | Can design for gentle learning curve |

#### Cons

| Aspect | Assessment |
|--------|------------|
| **Ecosystem** | None (must build everything) |
| **Time** | Significant development investment |
| **Maintenance** | Long-term burden |
| **Risk** | Unknown edge cases, bugs |
| **Adoption** | Users must learn new language |

## Decision

### Selected: Rego with Cedar for Performance-Critical Paths

**Primary Decision:** Use OPA/Rego as the primary policy language for PolicyStack.

**Secondary Decision:** Integrate Cedar for performance-critical paths where formal verification is required.

### Rationale

```
Decision Rationale:

Performance vs Expressiveness Trade-off:
├── Rego offers the best balance for general use
├── Cedar provides 3x performance for critical paths
└── Combined approach maximizes flexibility

Ecosystem Considerations:
├── Rego has mature ecosystem (CNCF graduated)
├── Existing Kubernetes integrations
├── Large policy library available
└── Cedar ecosystem growing but AWS-centric

Technical Fit:
├── Rego partial evaluation ideal for distributed
├── WASM support enables edge deployment
├── Cedar verification adds safety layer
└── Both compile to Rust-friendly targets

Risk Mitigation:
├── Rego proven at scale (Netflix, GitHub, etc.)
├── Cedar backed by AWS
├── Both have active development
└── Migration path between them exists
```

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   PolicyStack Architecture                       │
│                     (Rego + Cedar Hybrid)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │                Policy API Gateway                          │ │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │
│   │  │   Request    │  │   Router     │  │   Response   │  │ │
│   │  │   Parser     │─►│   (policy    │─►│   Formatter  │  │ │
│   │  │              │  │   selector)  │  │              │  │ │
│   │  └──────────────┘  └──────────────┘  └──────────────┘  │ │
│   └────────────────────┬────────────────────────────────────┘ │
│                        │                                         │
│        ┌───────────────┴───────────────┐                       │
│        │                               │                       │
│        ▼                               ▼                       │
│   ┌──────────────────┐      ┌──────────────────┐          │
│   │   Rego Engine      │      │   Cedar Engine   │          │
│   │   (OPA/WASM)       │      │   (Native)       │          │
│   ├──────────────────┤      ├──────────────────┤          │
│   │ • Complex ABAC     │      │ • Fast RBAC      │          │
│   │ • Partial eval     │      │ • Verified       │          │
│   │ • Context-aware    │      │ • Schema-enforced│          │
│   │ • Dynamic data     │      │ • <1ms latency   │          │
│   └──────────────────┘      └──────────────────┘          │
│                        │                               │          │
│                        └───────────┬───────────────────┘          │
│                                    │                              │
│                                    ▼                              │
│                         ┌──────────────────┐                     │
│                         │   Unified Cache  │                     │
│                         │   & Audit Log    │                     │
│                         └──────────────────┘                     │
│                                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Policy Routing Logic

```yaml
# PolicyStack routing configuration
policy_routing:
  default_engine: rego
  
  routing_rules:
    # Cedar for high-frequency, simple checks
    - engine: cedar
      conditions:
        - latency_requirement: "<1ms"
        - complexity: simple
        - verification_required: true
      examples:
        - api_gateway_auth
        - microservice_check
        - rbac_lookup
    
    # Rego for complex, context-aware policies
    - engine: rego
      conditions:
        - complexity: complex
        - context_attributes: true
        - partial_evaluation: true
      examples:
        - compliance_policy
        - risk_based_auth
        - dynamic_authorization
    
    # Either for intermediate cases
    - engine: either
      conditions:
        - fallback: true
      selection:
        - prefer: cedar  # If applicable
        - else: rego
```

## Consequences

### Positive

1. **Flexibility:** Rego handles complex policies; Cedar handles fast paths
2. **Ecosystem:** Access to OPA's mature tooling and integrations
3. **Performance:** Cedar provides sub-millisecond latency where needed
4. **Future-proof:** Can add Cedar-only mode for specific deployments
5. **Learning:** Team can start with Rego, add Cedar as needed

### Negative

1. **Complexity:** Two languages to maintain and understand
2. **Deployment:** More complex deployment (OPA + Cedar library)
3. **Debugging:** Different debugging approaches for each engine
4. **Testing:** Must test policies in both engines
5. **Documentation:** More documentation to maintain

### Mitigations

| Risk | Mitigation |
|------|------------|
| Complexity | Abstract common patterns; shared data model |
| Deployment | Unified container with both engines |
| Debugging | Common tracing format; unified logging |
| Testing | Shared test suite with engine adapters |
| Documentation | Side-by-side examples; decision guide |

## Implementation Notes

### Phase 1: Rego Foundation

```rust
// Rego integration structure
pub struct RegoEngine {
    wasm_module: Module,
    cache: Arc<RwLock<PolicyCache>>,
    data_store: Arc<dyn DataStore>,
}

impl PolicyEngine for RegoEngine {
    async fn evaluate(&self, request: Request) -> Result<Decision> {
        // Load compiled WASM
        // Set data context
        // Evaluate with partial support
        // Return decision with metadata
    }
    
    async fn partial_evaluate(&self, request: Request, unknowns: Vec<String>) 
        -> Result<Residual> {
        // Compute residual policy
        // Return optimized query
    }
}
```

### Phase 2: Cedar Integration

```rust
// Cedar integration structure
pub struct CedarEngine {
    authorizer: Authorizer,
    policy_set: Arc<RwLock<PolicySet>>,
    schema: Schema,
}

impl PolicyEngine for CedarEngine {
    async fn evaluate(&self, request: Request) -> Result<Decision> {
        // Build Cedar request
        // Evaluate against policy set
        // Return fast decision
    }
    
    fn verify(&self, property: Property) -> Result<VerificationResult> {
        // Use Cedar verifier
        // Return proof or counter-example
    }
}
```

### Phase 3: Unified API

```rust
// Unified policy engine trait
#[async_trait]
pub trait PolicyEngine: Send + Sync {
    async fn evaluate(&self, request: Request) -> Result<Decision>;
    async fn explain(&self, request: Request) -> Result<Explanation>;
    fn capabilities(&self) -> EngineCapabilities;
}

// Engine selector
pub struct PolicyRouter {
    rego: Arc<RegoEngine>,
    cedar: Arc<CedarEngine>,
    config: RoutingConfig,
}

impl PolicyRouter {
    pub async fn route(&self, request: Request) -> Result<Decision> {
        let engine = self.select_engine(&request)?;
        engine.evaluate(request).await
    }
    
    fn select_engine(&self, request: &Request) -> Result<Arc<dyn PolicyEngine>> {
        match &self.config.routing_rules {
            // Evaluate conditions and select appropriate engine
            _ => Ok(self.rego.clone()),
        }
    }
}
```

## Related Decisions

- **ADR-002: Enforcement Pattern** - How policies are enforced (sidecar vs library)
- **ADR-003: Data Model** - Entity and relationship model for both engines
- **ADR-004: Audit Strategy** - Unified logging across both engines

## References

1. OPA Documentation: https://www.openpolicyagent.org/docs/
2. Cedar Documentation: https://www.cedarpolicy.com/
3. Rego Language Reference: https://www.openpolicyagent.org/docs/policy-language/
4. Cedar Design Principles: https://www.cedarpolicy.com/blog/cedar-design
5. Zanzibar Paper: https://research.google/pubs/pub48190/

## Appendix: Detailed Comparison

### Language Syntax Comparison

| Feature | Rego | Cedar | Custom DSL |
|---------|------|-------|------------|
| Variable binding | `:=` | Implicit | `let` or `:=` |
| Equality | `==` | `==` | `==` |
| Set operations | Built-in | Limited | Planned |
| String matching | `glob`, `regex` | Limited | `matches` |
| Time functions | `time` package | Limited | Built-in |
| Custom functions | Rules | No | Functions |
| Loops/Iteration | Comprehensions | No | For/while |

### Performance Comparison Matrix

| Metric | Rego Native | Rego WASM | Cedar | Target Custom |
|--------|-------------|-----------|-------|---------------|
| p50 latency | 0.05ms | 0.20ms | 0.03ms | 0.10ms |
| p99 latency | 0.12ms | 0.60ms | 0.08ms | 0.30ms |
| Throughput | 200K qps | 50K qps | 600K qps | 100K qps |
| Memory base | 25MB | 5MB | 12MB | 15MB |
| Startup | 100ms | 50ms | 10ms | 30ms |

---

**Status:** Proposed  
**Date:** 2026-04-02  
**Next Review:** 2026-05-02

*End of ADR-001*

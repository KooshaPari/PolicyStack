# State of the Art: Authorization Models

Comprehensive research on authorization models, patterns, and architectural approaches for modern access control systems. This document provides the foundational understanding for PolicyStack's authorization model design.

**Document Version:** 1.0.0  
**Last Updated:** 2026-04-02  
**Research Scope:** Authorization models (RBAC, ABAC, ReBAC), composition patterns, and implementation strategies.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Access Control Lists (ACL)](#1-access-control-lists-acl)
3. [Role-Based Access Control (RBAC)](#2-role-based-access-control-rbac)
4. [Attribute-Based Access Control (ABAC)](#3-attribute-based-access-control-abac)
5. [Relationship-Based Access Control (ReBAC)](#4-relationship-based-access-control-rebac)
6. [Policy Composition Patterns](#5-policy-composition-patterns)
7. [Model Selection Framework](#6-model-selection-framework)
8. [Hybrid Approaches](#7-hybrid-approaches)
9. [Implementation Considerations](#8-implementation-considerations)
10. [References](#9-references)

---

## Executive Summary

Authorization models define how access decisions are made in software systems. Over decades of evolution, models have progressed from simple lists to sophisticated relationship-aware systems.

**Evolution Timeline:**

```
1960s: ACL (Multics, early UNIX)
   │
1992: RBAC (Ferraiolo & Kuhn, NIST standardization)
   │
2003: ABAC (XACML standard, NIST framework)
   │
2016: ReBAC (Google Zanzibar paper)
   │
2019+: Modern implementations (OPA, Cedar, OpenFGA)
```

**Model Comparison at a Glance:**

| Model | Granularity | Complexity | Scalability | Auditability |
|-------|-------------|------------|-------------|--------------|
| ACL | Resource-level | Low | Poor | Poor |
| RBAC | Role-level | Medium | Good | Good |
| ABAC | Fine-grained | High | Medium | Medium |
| ReBAC | Relationship | Medium | Excellent | Good |

---

## 1. Access Control Lists (ACL)

### 1.1 Basic Concept

ACLs associate a list of permissions with each protected resource. Each entry specifies a user or group and their allowed actions.

```
Resource: /documents/annual-report.pdf
┌─────────────────────────────────────┐
│ ACL                                 │
├─────────────────────────────────────┤
│ alice: read, write                  │
│ bob: read                           │
│ finance-team: read, write           │
│ *: read                             │
└─────────────────────────────────────┘
```

### 1.2 ACL Types

**Discretionary ACL (DACL):**
- Resource owners control access
- Common in file systems (NTFS, ext4)
- Flexible but prone to privilege creep

**System ACL (SACL):**
- Used for audit logging
- Defines what events to record
- Separate from access decisions

**Mandatory ACL (MACL):**
- System-enforced, users cannot modify
- Used in high-security environments
- Often combined with classification labels

### 1.3 ACL Representation Formats

```json
{
  "resource": "doc-123",
  "acl": [
    {
      "principal": "user:alice",
      "permissions": ["read", "write", "delete"]
    },
    {
      "principal": "group:finance",
      "permissions": ["read"]
    },
    {
      "principal": "user:bob",
      "permissions": ["read"],
      "conditions": {
        "time_based": {
          "start": "09:00",
          "end": "17:00"
        }
      }
    }
  ]
}
```

### 1.4 ACL Limitations

```
Scalability Issues:
├── O(n) lookup per resource (n = number of entries)
├── Permission inheritance difficult
├── Cross-resource queries expensive
├── Permission review is O(all resources × all users)
└── Revocation requires updating all resources

Management Issues:
├── No role abstraction
├── Permission explosion with many users
├── Difficult to answer "what can X access?"
└── No transitive permissions
```

### 1.5 When to Use ACLs

- **Simple systems:** Few users, few resources
- **File systems:** Native ACL support
- **Coarse-grained access:** Binary allow/deny
- **Static environments:** Rarely changing permissions

---

## 2. Role-Based Access Control (RBAC)

### 2.1 Core Model (RBAC96 Standard)

```
RBAC96 Components:
├── Users (U)
├── Roles (R)
├── Permissions (P)
├── Sessions (S)
├── UA ⊆ U × R (User-Role Assignment)
├── PA ⊆ P × R (Permission-Role Assignment)
└── RH ⊆ R × R (Role Hierarchy)
```

### 2.2 RBAC Levels

#### 2.2.1 RBAC0 (Core)

Basic role-permission model without hierarchy.

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    User      │      │     Role     │      │  Permission  │
├──────────────┤      ├──────────────┤      ├──────────────┤
│ alice        │◄────►│ admin        │◄────►│ user:read    │
│ bob          │  UA  │ editor       │  PA  │ user:write   │
│ carol        │      │ viewer       │      │ doc:delete   │
└──────────────┘      └──────────────┘      └──────────────┘
```

**Example Configuration:**

```yaml
# RBAC0 Configuration
users:
  - id: alice
    roles: [admin]
  - id: bob
    roles: [editor]
  - id: carol
    roles: [viewer]

roles:
  admin:
    permissions:
      - resource: user
        actions: [read, write, delete]
      - resource: document
        actions: [read, write, delete]
  
  editor:
    permissions:
      - resource: document
        actions: [read, write]
  
  viewer:
    permissions:
      - resource: document
        actions: [read]
```

#### 2.2.2 RBAC1 (Hierarchical)

Adds role hierarchy for permission inheritance.

```
Role Hierarchy:

         ┌─────────┐
         │  admin  │
         └────┬────┘
              │ inherits
              ▼
         ┌─────────┐
         │ editor  │
         └────┬────┘
              │ inherits
              ▼
         ┌─────────┐
         │ viewer  │
         └─────────┘

admin has: admin + editor + viewer permissions
editor has: editor + viewer permissions
viewer has: viewer permissions only
```

**Implementation Patterns:**

```python
# Hierarchical role resolution
def get_effective_permissions(user_roles, role_hierarchy):
    """Resolve role hierarchy to get all effective permissions."""
    effective_roles = set()
    
    def expand_role(role):
        effective_roles.add(role)
        # Add inherited roles
        for parent in role_hierarchy.get_parents(role):
            expand_role(parent)
    
    for role in user_roles:
        expand_role(role)
    
    # Collect all permissions
    permissions = set()
    for role in effective_roles:
        permissions.update(role_permissions[role])
    
    return permissions
```

#### 2.2.3 RBAC2 (Constraints)

Adds separation of duty constraints.

```
Static Separation of Duty (SSoD):
├── Mutually exclusive roles
│   Example: approver and requestor cannot be same user
├── Cardinality constraints
│   Example: Maximum 3 admins
└── Prerequisite roles
    Example: Must be senior_dev before architect

Dynamic Separation of Duty (DSoD):
├── Session-based constraints
│   Example: Cannot activate conflicting roles in same session
├── Temporal constraints
│   Example: admin role only during business hours
└── Context-based constraints
    Example: manager role only for user's department
```

**Constraint Definition:**

```yaml
constraints:
  static:
    - type: mutually_exclusive
      roles: [approver, requestor]
      description: "Cannot have both approval and request roles"
    
    - type: cardinality
      role: admin
      max: 5
      description: "Maximum 5 system administrators"
  
  dynamic:
    - type: session_exclusive
      roles: [cashier, auditor]
      description: "Cannot activate both in same session"
    
    - type: time_based
      role: admin
      allowed_hours: [9, 17]
      timezone: "America/New_York"
```

#### 2.2.4 RBAC3 (Combined)

Full RBAC with hierarchy and constraints.

```
RBAC3 Model:
├── RBAC0 (Core)
├── RBAC1 (Hierarchy)
└── RBAC2 (Constraints)
```

### 2.3 RBAC Variants

#### 2.3.1 Hierarchical RBAC (HRBAC)

```
Resource Hierarchy:

Organization
├── Department: Engineering
│   ├── Team: Platform
│   │   ├── Service: Auth
│   │   └── Service: API
│   └── Team: Frontend
│       ├── App: Web
│       └── App: Mobile
└── Department: Sales
    └── ...

Permission inheritance flows down the hierarchy.
```

#### 2.3.2 Temporal RBAC (TRBAC)

```python
class TemporalRoleManager:
    """RBAC with time-based activation."""
    
    def is_role_active(self, user, role, timestamp):
        role_assignment = self.get_assignment(user, role)
        
        # Check temporal constraints
        if role_assignment.valid_from > timestamp:
            return False
        if role_assignment.valid_until < timestamp:
            return False
        
        # Check periodic constraints
        if role_assignment.schedule:
            return self.matches_schedule(
                timestamp, 
                role_assignment.schedule
            )
        
        return True
```

#### 2.3.3 Task-Based RBAC (T-RBAC)

```
Workflow Integration:

Task: "Review Expense Report"
├── Required Roles: [manager]
├── Temporary Grants:
│   └── Reviewer gets "expense:read" for this report only
├── Duration: Until task completion
└── Revocation: Automatic on completion
```

### 2.4 RBAC Implementation Patterns

#### 2.4.1 Flat Role Table

```sql
-- Simple RBAC schema
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE roles (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE permissions (
    id UUID PRIMARY KEY,
    resource VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    UNIQUE(resource, action)
);

CREATE TABLE role_permissions (
    role_id UUID REFERENCES roles(id),
    permission_id UUID REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);
```

#### 2.4.2 Graph-Based RBAC

```
Graph Schema for Neo4j:

(:User)-[:HAS_ROLE {granted_at, expires_at}]->(:Role)
(:Role)-[:INHERITS_FROM*]->(:Role)
(:Role)-[:HAS_PERMISSION]->(:Permission)
(:Permission)-[:ON_RESOURCE]->(:Resource)

Query: What can Alice do?
```cypher
MATCH (u:User {name: "alice"})-[:HAS_ROLE]->(r:Role)
MATCH (r)-[:INHERITS_FROM*0..]->(inherited:Role)
MATCH (inherited)-[:HAS_PERMISSION]->(p:Permission)
RETURN collect(DISTINCT p.name) AS permissions
```
```

### 2.5 RBAC Best Practices

```
Design Principles:
├── Role Naming
│   ├── Functional names (billing_admin, not admin_level_3)
│   ├── Consistent prefixing (dept:engineering:lead)
│   └── Avoid person-based roles (johns_permissions)
├── Granularity
│   ├── Task-based roles over identity-based
│   ├── Minimize role overlap
│   └── Review role usage quarterly
├── Hierarchy
│   ├── Keep depth <= 3
│   ├── Avoid diamond inheritance
│   └── Document inheritance chains
└── Constraints
    ├── Apply SSoD for financial roles
    ├── Monitor constraint violations
    └── Regular access reviews
```

---

## 3. Attribute-Based Access Control (ABAC)

### 3.1 Core Model

ABAC makes authorization decisions based on attributes of subjects, resources, actions, and the environment.

```
ABAC Components:
├── Subject Attributes
│   ├── User ID
│   ├── Department
│   ├── Clearance Level
│   ├── Employment Status
│   └── Certifications
├── Resource Attributes
│   ├── Owner
│   ├── Classification
│   ├── Department
│   ├── Created Date
│   └── Tags
├── Action Attributes
│   ├── Type (read, write, delete)
│   ├── Sensitivity
│   └── Audit Level
└── Environment Attributes
    ├── Time of Day
    ├── Location
    ├── Device Trust Level
    └── Threat Level
```

### 3.2 XACML Architecture

```
XACML 3.0 Standard Architecture:

┌─────────────────────────────────────────────────────────────┐
│                        Policy Enforcement Point (PEP)          │
│                    (Intercepts access requests)              │
└────────────────────┬────────────────────────────────────────┘
                     │ XACML Request (XML/JSON)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                        Policy Decision Point (PDP)            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Policy    │  │   Policy    │  │    Policy           │ │
│  │  Retrieval  │->│  Combining  │->│   Evaluation        │ │
│  │             │  │  Algorithm  │  │  (target, condition)│ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│           │                                      │          │
│           ▼                                      ▼          │
│  ┌─────────────┐                        ┌─────────────────┐  │
│  │ Policy Store│                        │ Attribute Query │  │
│  │  (PAP)      │                        │     to PIP      │  │
│  └─────────────┘                        └─────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Attribute Values
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Policy Information Point (PIP)            │
│              (Resolves attributes from sources)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │   LDAP   │ │   HR DB  │ │ Device   │ │   Threat Intel   │ │
│  │          │ │          │ │ Registry │ │     Feed         │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼ XACML Response
┌─────────────────────────────────────────────────────────────┐
│                        Policy Administration Point (PAP)      │
│              (Policy authoring, testing, deployment)          │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 ABAC Policy Structure

#### 3.3.1 Simple Attribute Policy

```json
{
  "policy_id": "document-access-v1",
  "target": {
    "resource": {
      "type": "document",
      "attributes": {
        "classification": {
          "in": ["confidential", "secret"]
        }
      }
    },
    "action": {
      "id": "read"
    }
  },
  "rule": {
    "effect": "permit",
    "condition": {
      "apply": "and",
      "expressions": [
        {
          "apply": "greater-than-or-equal",
          "attribute": "subject.clearance_level",
          "value": "resource.classification_level"
        },
        {
          "apply": "equals",
          "attribute": "subject.department",
          "value": "resource.department"
        },
        {
          "apply": "in-range",
          "attribute": "environment.time",
          "range": ["09:00", "17:00"]
        }
      ]
    }
  }
}
```

#### 3.3.2 Complex Policy with Functions

```yaml
# ABAC Policy with custom functions
policy:
  id: secure-zone-access
  description: Access to secure zones with multi-factor validation
  
  target:
    resource:
      type: secure_zone
      
  rules:
    - effect: permit
      description: Department match with clearance
      condition:
        all:
          - subject.department == resource.owning_department
          - subject.security_clearance >= resource.required_clearance
          - subject.active_certifications contains resource.required_certification
          
    - effect: permit
      description: Emergency override with C-level approval
      condition:
        all:
          - subject.level in ["C1", "C2", "C3"]
          - context.emergency_declared == true
          - context.approver_verified == true
          - function: log_alert(
              level: "critical",
              message: "Emergency access granted",
              subject: subject.id,
              resource: resource.id
            )
            
    - effect: deny
      description: Block compromised accounts
      condition:
        any:
          - subject.account_status == "compromised"
          - subject.threat_score > 90
          - context.device.trust_level < 30
```

### 3.4 ABAC Patterns

#### 3.4.1 Dynamic Authorization

```python
class DynamicAuthorizer:
    """Real-time attribute-based authorization."""
    
    async def authorize(self, request: AuthzRequest) -> Decision:
        # Fetch fresh attributes
        subject_attrs = await self.pip.resolve_subject(
            request.subject_id,
            context=request.context
        )
        
        resource_attrs = await self.pip.resolve_resource(
            request.resource_id,
            context=request.context
        )
        
        env_attrs = await self.pip.resolve_environment(
            request.context
        )
        
        # Evaluate against policy
        policy = self.policy_store.get_policy(
            resource_attrs.get('policy_id')
        )
        
        decision = self.evaluator.evaluate(
            policy=policy,
            subject=subject_attrs,
            resource=resource_attrs,
            action=request.action,
            environment=env_attrs
        )
        
        # Log with full context
        await self.audit.log({
            'request': request,
            'attributes': {
                'subject': subject_attrs,
                'resource': resource_attrs,
                'environment': env_attrs
            },
            'decision': decision,
            'policy_id': policy.id
        })
        
        return decision
```

#### 3.4.2 Risk-Adaptive Authorization

```
Risk-Adaptive Model:

Base Attributes:
├── User: clearance=secret, dept=engineering
├── Resource: classification=confidential, dept=engineering
├── Environment: time=14:00, location=office
└── Risk Score: 30 (low)

Decision: ALLOW

─── Risk Event Occurs ───▶

Updated Environment:
├── Threat level: elevated
├── Unusual access pattern detected
├── Device posture: non-compliant
└── Risk Score: 85 (high)

Decision: DENY (or step-up MFA)
```

### 3.5 ABAC Implementation Strategies

#### 3.5.1 Attribute Resolution Architecture

```
Attribute Resolution Flow:

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Request   │────►│   PDP       │────►│   PIP       │
│             │     │   Cache     │     │   Router    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
          ┌──────────────────────────────────────┼──────────────────────┐
          │                                      │                      │
          ▼                                      ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Identity      │  │     HR          │  │   Device        │  │   Threat        │
│   Provider      │  │   System        │  │   Registry      │  │   Intel         │
│   (OIDC/LDAP)   │  │   (Database)    │  │   (MDM)         │  │   (API)         │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
          │                  │                  │                  │
          └──────────────────┴──────────────────┴──────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Attribute Cache  │
                    │  (TTL-based)      │
                    │  • Subject: 5min  │
                    │  • Resource: 1min │
                    │  • Env: 10sec     │
                    └─────────────────┘
```

#### 3.5.2 Attribute Caching Strategy

```python
class AttributeCache:
    """Multi-tier attribute cache with freshness guarantees."""
    
    def __init__(self):
        self.local_cache = LRUCache(maxsize=10000)
        self.distributed_cache = RedisCache()
        
    async def get_attribute(self, entity_type, entity_id, attr_name, freshness_required):
        cache_key = f"{entity_type}:{entity_id}:{attr_name}"
        
        # Check local cache first
        if cache_key in self.local_cache:
            value, timestamp = self.local_cache[cache_key]
            age = time.now() - timestamp
            
            if age < freshness_required:
                return value
        
        # Check distributed cache
        cached = await self.distributed_cache.get(cache_key)
        if cached:
            self.local_cache[cache_key] = (cached['value'], cached['timestamp'])
            return cached['value']
        
        # Fetch from source
        value = await self.fetch_from_source(entity_type, entity_id, attr_name)
        
        # Populate caches
        await self.distributed_cache.set(cache_key, {
            'value': value,
            'timestamp': time.now()
        }, ttl=self.get_ttl(entity_type))
        
        self.local_cache[cache_key] = (value, time.now())
        
        return value
```

### 3.6 ABAC Challenges

```
Common Challenges:
├── Attribute Consistency
│   ├── Stale attributes lead to wrong decisions
│   ├── Cross-system synchronization
│   └── Cache invalidation complexity
├── Performance
│   ├── Multiple attribute sources = latency
│   ├── Complex policy evaluation
│   └── Dynamic resolution overhead
├── Policy Complexity
│   ├── Rule explosion
│   ├── Debugging difficulty
│   └── Testing coverage
└── Governance
    ├── Attribute schema management
    ├── Policy lifecycle
    └── Compliance auditing
```

---

## 4. Relationship-Based Access Control (ReBAC)

### 4.1 Zanzibar Foundation

ReBAC is inspired by Google's Zanzibar paper (2019), which powers authorization across Google's services.

```
Zanzibar Core Concepts:

Tuple: (object, relation, user)
  Example: (doc:123, owner, user:alice)

Userset: Set of users defined by a relation
  Example: doc:123#viewer (all viewers of doc-123)

Rewrite Rule: Defines computed relations
  Example: viewer = owner + editor + viewer
```

### 4.2 ReBAC Model

#### 4.2.1 Tuple Structure

```
Tuple Format:

┌─────────────────────────────────────────────────────────┐
│  <object> # <relation> @ <user>                          │
│                                                          │
│  object    = <type> : <id>                               │
│  relation  = string (owner, editor, viewer, parent)      │
│  user      = <user_type> : <id> | <userset>              │
│  userset   = <object> # <relation>                     │
└─────────────────────────────────────────────────────────┘

Examples:
├── document:123#owner@user:alice
├── document:123#editor@group:eng#member
├── folder:abc#parent@folder:parent
└── document:123#viewer@folder:abc#viewer (indirect)
```

#### 4.2.2 Namespace Configuration

```yaml
# ReBAC Namespace Definition (OpenFGA style)
model:
  schema_version: "1.1"
  
  types:
    - type: user
    
    - type: organization
      relations:
        owner: [user]
        member: [user, organization#member]
        admin: [user]
      metadata:
        relations:
          member:
            directly_related_user_types:
              - user
              - organization#member  # Transitive membership
    
    - type: folder
      relations:
        owner: [user]
        parent: [folder]
        viewer: [user, user:*]  # Direct or public
        editor: [user]
      metadata:
        relations:
          viewer:
            union:
              - this  # Direct assignment
              - editor  # Editors are viewers
              - computed_userset: parent#viewer  # Inherited from parent
          editor:
            union:
              - this
              - computed_userset: parent#editor
```

### 4.3 ReBAC Patterns

#### 4.3.1 Hierarchical Permissions

```
Folder Hierarchy with Inheritance:

Organization
└── Engineering (owner: alice)
    ├── Platform (inherited: editor from parent)
    │   ├── API Gateway (inherited: viewer from parent)
    │   └── Auth Service (inherited: viewer from parent)
    └── Frontend (inherited: editor from parent)
        ├── Web App (inherited: viewer from parent)
        └── Mobile App (inherited: viewer from parent)

Permission Flow:
alice (org owner)
  └─► engineering#owner
        └─► engineering#editor (union)
              └─► platform#editor (inheritance)
                    └─► api-gateway#viewer (transitive)
```

#### 4.3.2 Social Graph Pattern

```yaml
# GitHub-style repository access
model:
  types:
    - type: user
    
    - type: team
      relations:
        member: [user, team#member]
        maintainer: [user]
      metadata:
        relations:
          member:
            union:
              - this
              - computed_userset: maintainer
    
    - type: repository
      relations:
        owner: [user]
        maintainer: [user, team#maintainer]
        writer: [user, team#member]
        reader: [user, user:*]
        parent_org: [organization]
      metadata:
        relations:
          reader:
            union:
              - this
              - writer
              - maintainer
              - owner
              - computed_userset: parent_org#member
```

#### 4.3.3 Multi-Tenant Isolation

```
Tenant Isolation Model:

Tenant A                    Tenant B
┌──────────────┐            ┌──────────────┐
│ Admin: alice│            │ Admin: bob   │
│             │            │              │
│ Resources:  │            │ Resources:   │
│ - doc:A1    │            │ - doc:B1     │
│ - doc:A2    │            │ - doc:B2     │
└──────────────┘            └──────────────┘

Strict Separation:
├── alice cannot access doc:B1 (different tenant)
├── bob cannot access doc:A1
└── Cross-tenant access requires explicit tuple
```

### 4.4 ReBAC Implementation

#### 4.4.1 Tuple Store Design

```sql
-- PostgreSQL schema for ReBAC
CREATE TABLE tuples (
    store_id VARCHAR(255) NOT NULL,
    object_type VARCHAR(128) NOT NULL,
    object_id VARCHAR(128) NOT NULL,
    relation VARCHAR(128) NOT NULL,
    user_type VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    user_relation VARCHAR(128),
    inserted_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (store_id, object_type, object_id, relation, user_type, user_id, user_relation)
);

-- Index for Check queries
CREATE INDEX idx_tuples_user_lookup ON tuples(
    store_id, user_type, user_id, object_type, relation
);

-- Index for ListObjects queries
CREATE INDEX idx_tuples_object_lookup ON tuples(
    store_id, object_type, object_id
);

-- Index for temporal queries
CREATE INDEX idx_tuples_inserted ON tuples(inserted_at);
```

#### 4.4.2 Check Algorithm

```python
async def check(store_id: str, tuple_key: TupleKey) -> bool:
    """
    Check if user has relation to object.
    Implements recursive resolution with cycle detection.
    """
    visited = set()
    
    async def resolve(object_type, object_id, relation, depth=0):
        if depth > MAX_DEPTH:
            raise ResolutionError("Maximum recursion depth exceeded")
        
        cache_key = f"{object_type}:{object_id}#{relation}"
        if cache_key in visited:
            return False
        visited.add(cache_key)
        
        # Get namespace configuration
        ns_config = await get_namespace_config(object_type)
        rewrite = ns_config.get_relation_rewrite(relation)
        
        # Evaluate rewrite rule
        if rewrite.type == "direct":
            # Check direct assignment
            tuples = await db.query_tuples(
                store_id=store_id,
                object_type=object_type,
                object_id=object_id,
                relation=relation,
                user=tuple_key.user
            )
            return len(tuples) > 0
        
        elif rewrite.type == "union":
            # Union of multiple sources
            for child in rewrite.children:
                if await resolve_child(child, object_type, object_id, depth):
                    return True
            return False
        
        elif rewrite.type == "intersection":
            # Must satisfy all
            for child in rewrite.children:
                if not await resolve_child(child, object_type, object_id, depth):
                    return False
            return True
        
        elif rewrite.type == "exclusion":
            # Base minus exclusion
            base_result = await resolve_child(
                rewrite.base, object_type, object_id, depth
            )
            if not base_result:
                return False
            
            exclude_result = await resolve_child(
                rewrite.exclude, object_type, object_id, depth
            )
            return not exclude_result
        
        return False
    
    return await resolve(
        tuple_key.object_type,
        tuple_key.object_id,
        tuple_key.relation
    )
```

### 4.5 ReBAC vs Other Models

```
When to Choose ReBAC:
├── Relationship-heavy domains
│   ├── Social networks
│   ├── File systems / hierarchies
│   ├── Organizations with nested groups
│   └── Multi-tenant SaaS
├── Need for recursive permissions
├── List queries ("what can X access?")
└── Google Zanzibar-style architecture

ReBAC Advantages:
├── Natural expression of hierarchies
├── Efficient recursive queries
├── Implicit permission inheritance
├── Strong consistency options
└── Proven at scale (Google)

ReBAC Trade-offs:
├── More complex than RBAC
├── Tuple management overhead
├── Read-time computation
├── Limited attribute support
└── Learning curve for developers
```

---

## 5. Policy Composition Patterns

### 5.1 Composition Strategies

```
Policy Composition Approaches:

1. Union (Permit if any allow)
   Policy A ──┐
              ├──► ALLOW if A ∨ B
   Policy B ──┘

2. Intersection (Permit only if all allow)
   Policy A ──┐
              ├──► ALLOW if A ∧ B
   Policy B ──┘

3. Override (Priority-based)
   Deny Policy ──┐
                 ├──► Deny overrides Allow
   Allow Policy ─┘

4. Cascade (Sequential evaluation)
   Check A ──► Check B ──► Check C
   (stop at first decision)
```

### 5.2 Deny-Override Pattern

```yaml
# Deny-Override Policy Composition
policy_set:
  combining_algorithm: deny_overrides
  
  policies:
    - id: block-compromised
      effect: deny
      priority: 100
      condition: subject.threat_score > 80
      
    - id: require-mfa-for-admin
      effect: deny
      priority: 90
      condition:
        all:
          - subject.roles contains "admin"
          - context.mfa_verified == false
          
    - id: rbac-base
      effect: permit
      priority: 10
      condition: rbac_check(subject, resource, action)
      
    - id: default-deny
      effect: deny
      priority: 0
```

### 5.3 Permit-Override Pattern

```yaml
# Permit-Override for Whitelist Approach
policy_set:
  combining_algorithm: permit_overrides
  
  policies:
    - id: emergency-access
      effect: permit
      priority: 100
      condition:
        context.emergency_mode == true
        subject.has_emergency_access_token == true
        
    - id: admin-full-access
      effect: permit
      priority: 90
      condition: subject.roles contains "superadmin"
      
    - id: standard-rbac
      effect: permit
      priority: 50
      condition: standard_rbac_check()
      
    - id: default-deny
      effect: deny
      priority: 0
```

### 5.4 First-Applicable Pattern

```yaml
# First-Applicable for Rule Chaining
policy_set:
  combining_algorithm: first_applicable
  
  policies:
    - id: deny-blocked-users
      condition: subject.status == "blocked"
      effect: deny
      
    - id: allow-owners
      condition: resource.owner == subject.id
      effect: permit
      
    - id: check-rbac
      condition: rbac_check(subject, resource, action)
      effect: permit
      
    - id: check-abac
      condition: abac_check(subject, resource, action, context)
      effect: permit
      
    - id: final-deny
      effect: deny
```

---

## 6. Model Selection Framework

### 6.1 Decision Matrix

```
Model Selection by Requirements:

┌─────────────────────────────────────────────────────────────────────┐
│ Requirement              │ ACL │ RBAC │ ABAC │ ReBAC │ Hybrid     │
├─────────────────────────────────────────────────────────────────────┤
│ Simple system            │  ★  │  ★   │  ○   │  ○    │  ○         │
│ Many users/resources     │  ○  │  ★   │  ★   │  ★    │  ★         │
│ Role hierarchy needed    │  ✗  │  ★   │  ○   │  ★    │  ★         │
│ Attribute-based rules    │  ✗  │  ○   │  ★   │  ○    │  ★         │
│ Relationship queries     │  ✗  │  ○   │  ○   │  ★    │  ★         │
│ Compliance auditing      │  ○  │  ★   │  ★   │  ★    │  ★         │
│ Low latency required     │  ★  │  ★   │  ○   │  ★    │  ○         │
│ Complex policies         │  ✗  │  ○   │  ★   │  ○    │  ★         │
│ Developer simplicity     │  ★  │  ★   │  ○   │  ○    │  ○         │
└─────────────────────────────────────────────────────────────────────┘

★ = Excellent fit    ★ = Good fit    ○ = Possible    ✗ = Poor fit
```

### 6.2 Selection Flowchart

```
                    ┌─────────────────┐
                    │  Access Control  │
                    │    Decision     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Simple system?   │
                    │ (< 100 users)    │
                    └────────┬────────┘
                             │
            ┌────────────────┴────────────────┐
            │ YES                              │ NO
            ▼                                  ▼
    ┌───────────────┐              ┌───────────────────┐
    │     ACL       │              │ Role hierarchy?  │
    │   or RBAC     │              └────────┬──────────┘
    └───────────────┘                       │
                              ┌─────────────┴───────────────┐
                              │ YES                          │ NO
                              ▼                              ▼
                      ┌───────────────┐              ┌───────────────┐
                      │     RBAC      │              │ Attribute     │
                      │  (hierarchical)│              │ conditions?   │
                      └───────────────┘              └───────┬───────┘
                                                             │
                                            ┌────────────────┴───────────────┐
                                            │ YES                              │ NO
                                            ▼                                  ▼
                                    ┌───────────────┐              ┌───────────────┐
                                    │     ABAC      │              │ Relationships │
                                    │               │              │ important?    │
                                    └───────────────┘              └───────┬───────┘
                                                                           │
                                                          ┌────────────────┴───────────┐
                                                          │ YES                          │ NO
                                                          ▼                              ▼
                                                  ┌───────────────┐          ┌───────────────┐
                                                  │     ReBAC     │          │   Standard    │
                                                  │               │          │     RBAC      │
                                                  └───────────────┘          └───────────────┘
```

### 6.3 Domain-Specific Recommendations

| Domain | Recommended Model | Alternative |
|--------|-------------------|-------------|
| Banking/Finance | RBAC + ABAC | Cedar (verification) |
| Healthcare | ABAC (patient context) | RBAC (staff) |
| SaaS Platform | ReBAC (tenants) + RBAC (roles) | ABAC |
| E-commerce | RBAC + ABAC (fraud) | ReBAC (social) |
| Social Network | ReBAC | ABAC |
| Government | ABAC (clearance) + RBAC | MAC |
| API Gateway | RBAC (simple) / ABAC (complex) | Cedar |
| Kubernetes | RBAC (native) + OPA (policy) | Cedar |

---

## 7. Hybrid Approaches

### 7.1 RBAC + ABAC Hybrid

```yaml
# Tiered Authorization: RBAC for roles, ABAC for context
authorization:
  # Level 1: Role check (fast, cached)
  rbac_layer:
    enabled: true
    roles:
      admin:
        permissions: ["*:*"]
      manager:
        permissions: ["expense:read", "expense:approve"]
      employee:
        permissions: ["expense:read:own", "expense:create"]
  
  # Level 2: ABAC refinement
  abac_layer:
    enabled: true
    policies:
      - name: "time-based-restriction"
        condition:
          if: subject.roles contains "admin"
          then: true  # No restriction
          else:
            environment.time.hour >= 9
            environment.time.hour < 17
            
      - name: "location-based"
        condition:
          if: action.sensitivity == "high"
          then: context.location == "office"
          else: true
          
      - name: "approval-limit"
        condition:
          if: action == "expense:approve"
          then: resource.amount <= subject.approval_limit
          else: true
```

### 7.2 RBAC + ReBAC Hybrid

```yaml
# Organization structure with roles
model:
  types:
    - type: user
      attributes:
        global_roles: [superadmin, auditor]
    
    - type: organization
      relations:
        member: [user]
        admin: [user]
      metadata:
        # RBAC within org context
        roles:
          admin:
            permissions: [org:admin, org:read]
          member:
            permissions: [org:read]
            
    - type: project
      relations:
        org: [organization]
        owner: [user]
        member: [user, organization#member]
      metadata:
        # Inherit org membership
        member:
          union:
            - this
            - computed_userset: org#member
        # Project-specific roles
        roles:
          owner: [project:admin, project:read, project:write]
          member: [project:read]
```

### 7.3 Tiered Authorization

```
Tiered Evaluation:

Layer 1: Static (cacheable)
├── User roles
├── Group memberships
├── Resource ownership
└── Latency: < 1ms

Layer 2: Semi-static (short TTL cache)
├── Department membership
├── Project assignments
├── Certification status
└── Latency: < 5ms

Layer 3: Dynamic (real-time)
├── Current location
├── Device trust score
├── Threat level
├── Time-based rules
└── Latency: < 20ms

Layer 4: Policy evaluation
├── Complex ABAC rules
├── Risk scoring
├── Multi-factor requirements
└── Latency: < 50ms

Optimization: Early exit at any layer
```

---

## 8. Implementation Considerations

### 8.1 Performance Optimization

```
Caching Strategy:

┌─────────────────────────────────────────────────────────────┐
│                    Authorization Cache Hierarchy            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  L1: Local In-Memory                                          │
│  ├── Subject roles: 5 min TTL                                │
│  ├── Resource ACL: 1 min TTL                                 │
│  └── Decision cache: 30 sec TTL (with invalidation)          │
│                                                               │
│  L2: Distributed (Redis/Memcached)                           │
│  ├── Subject attributes: 5 min TTL                           │
│  ├── Resource metadata: 1 min TTL                            │
│  └── Policy versions: 10 min TTL                             │
│                                                               │
│  L3: Local Policy Cache                                       │
│  ├── Compiled policies: Until policy update                   │
│  └── Attribute schemas: Until schema update                   │
│                                                               │
│  Invalidation:                                                │
│  ├── Event-driven (user role change)                        │
│  ├── Time-based (TTL expiry)                                  │
│  └── Version-based (policy deployment)                       │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Audit and Compliance

```yaml
# Comprehensive audit logging
audit:
  log_all_decisions: true
  
  log_format:
    timestamp: ISO8601
    request_id: uuid
    decision_id: uuid
    
    subject:
      id: string
      attributes: object
      roles: [string]
      
    resource:
      id: string
      type: string
      attributes: object
      
    action:
      type: string
      context: object
      
    environment:
      time: timestamp
      location: string
      device_id: string
      
    policy:
      id: string
      version: string
      rules_applied: [string]
      
    decision:
      result: allow | deny
      reason: string
      duration_ms: number
      
    compliance:
      sox_relevant: boolean
      pci_scope: boolean
      retention_days: 2555  # 7 years
```

### 8.3 Testing Strategy

```python
# Authorization testing framework
class AuthorizationTestSuite:
    """Comprehensive tests for authorization system."""
    
    def test_rbac_hierarchy(self):
        """Verify role inheritance works correctly."""
        admin = create_user(roles=["admin"])
        assert can_do(admin, "read")
        assert can_do(admin, "write")
        assert can_do(admin, "delete")
        
    def test_abac_conditions(self):
        """Verify attribute-based rules."""
        user = create_user(clearance="secret")
        doc = create_resource(classification="top_secret")
        
        # Should deny
        assert not can_access(user, doc)
        
        # Upgrade clearance
        user.clearance = "top_secret"
        assert can_access(user, doc)
        
    def test_rebac_inheritance(self):
        """Verify relationship-based permissions."""
        folder = create_folder()
        doc = create_document(parent=folder)
        user = create_user()
        
        # Grant on folder
        grant(user, "viewer", folder)
        
        # Should inherit to document
        assert can_do(user, "read", doc)
        
    def test_policy_composition(self):
        """Verify deny-override semantics."""
        user = create_user(roles=["admin"])
        
        # Admin allows
        assert can_do(user, "action")
        
        # Add deny policy
        add_policy(deny_for(user, "action"))
        
        # Deny should override
        assert not can_do(user, "action")
        
    def test_performance_sla(self):
        """Verify latency requirements."""
        latencies = []
        for _ in range(1000):
            start = time.now()
            authorize(request)
            latencies.append(time.now() - start)
        
        p99 = percentile(latencies, 99)
        assert p99 < 10  # 10ms SLA
```

---

## 9. References

### 9.1 Standards

1. **NIST RBAC Standard** (ANSI/INCITS 359-2004)
2. **XACML 3.0** (eXtensible Access Control Markup Language)
3. **OAuth 2.0** (RFC 6749) - Authorization delegation
4. **UMA 2.0** (User-Managed Access)

### 9.2 Research Papers

1. Sandhu, R., et al. "Role-Based Access Control Models" (1996)
2. Yuan, E., Tong, J. "Attributed Based Access Control" (2005)
3. Google. "Zanzibar: Google's Consistent, Global Authorization System" (2019)
4. Backes, M., et al. "Relationships and Access Control" (2021)

### 9.3 Industry Resources

1. OPA Documentation: https://www.openpolicyagent.org/
2. OpenFGA Documentation: https://openfga.dev/
3. AWS Cedar Documentation: https://www.cedarpolicy.com/
4. Casbin Documentation: https://casbin.org/

---

## Document Metadata

- **Author:** PolicyStack Research Team
- **Review Cycle:** Quarterly
- **Next Review:** 2026-07-02
- **Status:** Draft v1.0

---

*End of Document - AUTHORIZATION_MODELS_SOTA.md*

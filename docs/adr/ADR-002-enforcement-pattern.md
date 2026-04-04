# ADR-002: Policy Enforcement Pattern

**Status:** Proposed  
**Date:** 2026-04-02  
**Authors:** PolicyStack Architecture Team  
**Reviewers:** Engineering Leadership, Security Team, DevOps Team

---

## Context

PolicyStack must determine how policy enforcement is integrated into application architectures. This decision impacts deployment complexity, latency characteristics, reliability guarantees, and operational overhead. We evaluate three primary enforcement patterns:

1. **Sidecar Pattern** - Co-located policy engine as separate container
2. **Library/Embedded Pattern** - Policy engine linked directly into application
3. **Proxy/Gateway Pattern** - Centralized enforcement at infrastructure layer

Additionally, we must decide between:
- **Synchronous Evaluation** - Blocking request for policy decision
- **Asynchronous Evaluation** - Non-blocking with eventual consistency

This ADR analyzes these patterns in depth, considering the diverse deployment scenarios PolicyStack must support—from Kubernetes-native microservices to serverless functions to edge deployments.

---

## Decision Drivers

| Driver | Weight | Description |
|--------|--------|-------------|
| **Latency** | 25% | Impact on request processing time |
| **Availability** | 20% | System resilience and fault tolerance |
| **Operational Complexity** | 15% | Deployment, monitoring, maintenance burden |
| **Scalability** | 15% | Ability to handle growth in traffic and policies |
| **Security Isolation** | 15% | Sandbox strength and blast radius containment |
| **Deployment Flexibility** | 10% | Support for diverse runtime environments |

---

## Option 1: Sidecar Pattern

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Kubernetes Pod                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │    Application Container    │    │         PolicyStack Sidecar         │ │
│  │                             │    │                                     │ │
│  │  ┌───────────────────────┐  │    │  ┌───────────┐  ┌──────────────┐  │ │
│  │  │    Application Code   │  │    │  │   Policy  │  │   WASM       │  │ │
│  │  │                       │  │    │  │   Store   │  │   Engine     │  │ │
│  │  │  ┌─────────────────┐  │  │    │  │           │  │              │  │ │
│  │  │  │ Policy Client   │──┼──┼────┼─►│  Rego     │  │  ┌────────┐  │  │ │
│  │  │  │ (lightweight)   │  │  │    │  │  Cedar    │  │  │Policy  │  │  │ │
│  │  │  └─────────────────┘  │  │    │  │  Policies │  │  │Eval    │  │  │ │
│  │  └───────────────────────┘  │    │  │           │  │  └────────┘  │  │ │
│  │                             │    │  └───────────┘  └──────────────┘  │ │
│  └─────────────────────────────┘    │           │                        │ │
│                                     │           ▼                        │ │
│                                     │  ┌──────────────────────────────┐  │ │
│                                     │  │     Local Data Cache         │  │ │
│                                     │  │  • User roles                │  │ │
│                                     │  │  • Resource attributes       │  │ │
│                                     │  │  • Policy bundles            │  │ │
│                                     │  └──────────────────────────────┘  │ │
│                                     │                                     │ │
│                                     │  ┌──────────────────────────────┐  │ │
│                                     │  │    Policy Control Plane      │  │ │
│                                     │  │         Connection           │  │ │
│                                     │  └──────────────────────────────┘  │ │
│                                     └─────────────────────────────────────┘ │
│                                                                              │
│  Shared Resources:                                                           │
│  • Network namespace (localhost communication)                              │
│  • Optional: Shared memory for high-performance IPC                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sidecar Communication Patterns

#### Pattern A: HTTP/gRPC Local Communication

```yaml
# Sidecar configuration
sidecar:
  server:
    bind_address: "127.0.0.1:8181"
    protocol: grpc
    
  # mTLS between app and sidecar (optional but recommended)
  security:
    mutual_tls:
      enabled: true
      cert_path: /etc/certs/sidecar.crt
      key_path: /etc/certs/sidecar.key
      ca_path: /etc/certs/ca.crt

  # Policy evaluation endpoints
  endpoints:
    evaluate: /v1/evaluate
    evaluate_batch: /v1/evaluate/batch
    explain: /v1/explain
    health: /healthz
```

```python
# Application client example
import grpc
from policystack.sidecar import PolicyClient

class PolicySidecarClient:
    """Lightweight client for sidecar communication."""
    
    def __init__(self, endpoint="localhost:8181"):
        self.channel = grpc.insecure_channel(endpoint)
        self.stub = PolicyStub(self.channel)
        
    async def authorize(self, request: AuthzRequest) -> Decision:
        """Evaluate authorization request via sidecar."""
        try:
            response = await self.stub.Evaluate(
                EvaluateRequest(
                    input=request.to_json(),
                    policy_id=request.policy_id,
                    trace=request.explain
                ),
                timeout=0.1  # 100ms timeout
            )
            return Decision.from_proto(response)
        except grpc.RpcError as e:
            # Fail closed - deny if sidecar unavailable
            return Decision(deny=True, reason=f"Policy engine unavailable: {e}")
```

#### Pattern B: Shared Memory IPC (High Performance)

```rust
// High-performance shared memory communication
use shmipc::{SharedMemory, RingBuffer};

pub struct ShmPolicyClient {
    request_buffer: RingBuffer<Request>,
    response_buffer: RingBuffer<Response>,
}

impl ShmPolicyClient {
    pub fn evaluate(&self, request: Request) -> Result<Response, Error> {
        // Write request to shared memory
        self.request_buffer.write(request)?;
        
        // Wait for response (spin or futex)
        self.response_buffer.wait_for_response(
            timeout=Duration::from_micros(500)
        )
    }
}

// Latency: <50 microseconds (vs 500-1000 for HTTP)
```

### Sidecar Policy Distribution

```yaml
# Policy bundle distribution to sidecars
policy_distribution:
  source:
    type: control_plane  # or s3, git, configmap
    url: https://control-plane.policystack.io/v1/bundles
    auth:
      type: service_account_token
      
  synchronization:
    mode: pull  # or push
    interval: 30s
    
  # Delta updates for efficiency
  updates:
    type: delta  # or full
    compression: gzip
    
  # Hot reload without restart
  activation:
    strategy: atomic_swap  # or rolling
    rollback_on_error: true
```

```rust
// Sidecar policy management
pub struct PolicyManager {
    active_bundle: Arc<PolicyBundle>,
    update_channel: mpsc::Receiver<BundleUpdate>,
}

impl PolicyManager {
    async fn apply_update(&mut self, update: BundleUpdate) -> Result<(), Error> {
        // Validate new bundle
        update.validate_signature(&self.trust_anchor)?;
        update.validate_schema()?;
        
        // Compile policies
        let compiled = self.compiler.compile(&update.policies)?;
        
        // Atomic swap
        let new_bundle = Arc::new(compiled);
        
        // Update with minimal lock contention
        self.active_bundle.store(new_bundle, Ordering::Release);
        
        // Drain old bundle references
        self.garbage_collect_old_bundles();
        
        Ok(())
    }
}
```

### Sidecar Pros

| Aspect | Assessment |
|--------|------------|
| **Isolation** | Strong - policy engine crash doesn't affect app |
| **Language Agnostic** | Excellent - any app can use via HTTP/gRPC |
| **Resource Management** | Independent scaling and resource limits |
| **Hot Updates** | Policies update without app restart |
| **Debugging** | Independent logging and metrics |
| **Multi-tenancy** | Sidecar per tenant possible |

### Sidecar Cons

| Aspect | Assessment |
|--------|------------|
| **Latency** | Network hop adds 0.5-2ms overhead |
| **Resource Overhead** | Additional container per pod (20-50MB) |
| **Deployment Complexity** | Extra container to configure and monitor |
| **Cold Start** | Sidecar must start before app requests |
| **Network Dependency** | Local network must be available |

### Sidecar Performance Characteristics

```
Latency Breakdown (Sidecar):
┌─────────────────────────────────────────────────────────────┐
│ Network Stack (localhost)        ████████░░░░░░░░░░  0.3ms  │
│ Serialization/Deserialization  ██████░░░░░░░░░░░░░  0.2ms  │
│ Policy Evaluation                ██████████████████  0.5ms  │
│ Response Encoding                ████░░░░░░░░░░░░░░░  0.1ms  │
├─────────────────────────────────────────────────────────────┤
│ Total (p50)                                          1.1ms  │
│ Total (p99)                                          2.5ms  │
└─────────────────────────────────────────────────────────────┘

Comparison:
- Direct library call: 0.5ms (p50)
- Sidecar (HTTP): 1.1ms (p50)
- Sidecar (gRPC): 0.9ms (p50)
- Sidecar (Shared Memory): 0.6ms (p50)
```

---

## Option 2: Library/Embedded Pattern

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Application Process                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Application Binary                                    │ │
│  │                                                                        │ │
│  │  ┌──────────────────────┐    ┌──────────────────────────────────────┐  │ │
│  │  │  Application Code    │    │      PolicyStack Library             │  │ │
│  │  │                      │    │                                      │  │ │
│  │  │  ┌────────────────┐  │    │  ┌───────────┐    ┌──────────────┐   │  │ │
│  │  │  │ Business Logic │  │    │  │  Policy   │    │   Evaluator  │   │  │ │
│  │  │  │                │  │    │  │  Loader   │───►│   (WASM)     │   │  │ │
│  │  │  │ authz_call() ──┼──┼────┼─►│           │    │              │   │  │ │
│  │  │  │                │  │    │  └───────────┘    └──────────────┘   │  │ │
│  │  │  └────────────────┘  │    │                                      │  │ │
│  │  │                      │    │  ┌───────────┐    ┌──────────────┐   │  │ │
│  │  └──────────────────────┘    │  │  Cache    │    │   Compiler   │   │  │ │
│  │                            │  │  (LRU)    │    │   (Rego/     │   │  │ │
│  │                            │  │           │    │   Cedar)     │   │  │ │
│  │                            │  └───────────┘    └──────────────┘   │  │ │
│  │                            │                                      │  │ │
│  │                            │  ┌──────────────────────────────────┐│  │ │
│  │                            │  │  Policy Sync (background task)   ││  │ │
│  │                            │  │  • Poll control plane          ││  │ │
│  │                            │  │  • Watch file changes          ││  │ │
│  │                            │  │  • WebSocket push              ││  │ │
│  │                            │  └──────────────────────────────────┘│  │ │
│  │                            └──────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  Memory Layout:                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Application Memory (shared)                                          │  │
│  │ ┌──────────────┬──────────────┬──────────────┬──────────────────────┐ │  │
│  │ │ App Heap     │ Policy Cache │ Policy Code  │ Application Code     │ │  │
│  │ │              │ (50MB)       │ (20MB)       │                      │ │  │
│  │ └──────────────┴──────────────┴──────────────┴──────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Library Integration Patterns

#### Rust Native Integration

```rust
// Direct library integration
use policystack::{PolicyEngine, Request, Decision};

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // Initialize policy engine
    let engine = PolicyEngine::builder()
        .with_wasm_engine(WasmEngine::Wasmtime)
        .with_cache_size(10_000)
        .with_policy_source(PolicySource::ControlPlane {
            endpoint: "https://policies.example.com".into(),
            api_key: env!("POLICY_API_KEY"),
            poll_interval: Duration::from_secs(30),
        })
        .build()
        .await?;
    
    // Evaluate inline
    let decision = engine.evaluate(Request {
        subject: Subject::User(user.id),
        action: Action::Read,
        resource: Resource::Document(doc_id),
        context: Context {
            time: Utc::now(),
            location: request.ip_geo(),
        },
    }).await?;
    
    if decision.allow {
        serve_request().await
    } else {
        Err(Error::Forbidden(decision.reason))
    }
}
```

#### Node.js Integration (WASM)

```javascript
// JavaScript library integration via WASM
import { PolicyEngine } from '@policystack/sdk';

const engine = await PolicyEngine.init({
  wasmModule: await fs.readFile('./policy-engine.wasm'),
  policyBundle: await fetch('https://policies.example.com/bundle'),
  cacheSize: 10000,
});

// FastAPI-style middleware
app.use(async (req, res, next) => {
  const decision = await engine.evaluate({
    subject: { id: req.user.id, roles: req.user.roles },
    action: req.method.toLowerCase(),
    resource: { type: 'endpoint', path: req.path },
    context: { 
      timestamp: Date.now(),
      ip: req.ip,
    },
  });
  
  if (!decision.allow) {
    return res.status(403).json({
      error: 'Forbidden',
      reason: decision.reason,
      policy: decision.policy_id,
    });
  }
  
  next();
});
```

#### Python Integration

```python
# Python library integration
from policystack import PolicyEngine, Request, Subject, Resource

engine = PolicyEngine(
    wasm_path="policy-engine.wasm",
    policy_bundle_url="https://policies.example.com/bundle",
    cache_size=10000,
)

# FastAPI dependency
async def require_permission(
    action: str,
    resource_type: str,
    request: Request,
    user: User = Depends(get_current_user)
):
    decision = await engine.evaluate(Request(
        subject=Subject(id=user.id, roles=user.roles),
        action=action,
        resource=Resource(type=resource_type, id=request.path_params.get("id")),
        context={
            "time": datetime.utcnow().isoformat(),
            "ip": request.client.host,
        }
    ))
    
    if not decision.allow:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: {decision.reason}"
        )
    
    return user

# Usage in endpoint
@app.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    user: User = Depends(require_permission("read", "document"))
):
    return await fetch_document(doc_id)
```

### Library Policy Updates

```rust
// Background policy synchronization
pub struct PolicySync {
    engine: Arc<PolicyEngine>,
    source: Box<dyn PolicySource>,
}

impl PolicySync {
    async fn run(&self) -> Result<(), Error> {
        let mut interval = tokio::time::interval(Duration::from_secs(30));
        
        loop {
            interval.tick().await;
            
            match self.source.check_update().await {
                Ok(Some(update)) => {
                    if let Err(e) = self.engine.load_policies(update).await {
                        tracing::error!("Policy update failed: {}", e);
                    }
                }
                Ok(None) => {} // No update available
                Err(e) => {
                    tracing::error!("Policy check failed: {}", e);
                }
            }
        }
    }
}
```

### Library Pros

| Aspect | Assessment |
|--------|------------|
| **Latency** | Excellent - function call overhead only (~50μs) |
| **Resource Efficiency** | Shared memory, no duplication |
| **Simplicity** | Single binary/container to deploy |
| **Cold Start** | No additional startup time |
| **Data Access** | Direct access to application data structures |

### Library Cons

| Aspect | Assessment |
|--------|------------|
| **Language Lock-in** | Requires native library per language (Rust, Go, Node, Python, etc.) |
| **Crash Risk** | Policy engine crash affects entire application |
| **Memory Sharing** | Policy engine memory usage affects app resources |
| **Update Complexity** | App restart required for library updates |
| **Isolation** | Limited sandboxing within process |

### Library Performance Characteristics

```
Latency Breakdown (Library):
┌─────────────────────────────────────────────────────────────┐
│ Function Call Overhead           █░░░░░░░░░░░░░░░░░░░  0.05ms│
│ Request Serialization            ██░░░░░░░░░░░░░░░░░░  0.10ms│
│ Cache Lookup                     █░░░░░░░░░░░░░░░░░░░  0.03ms│
│ Policy Evaluation (WASM)         ██████████████████   0.50ms│
│ Result Deserialization           ██░░░░░░░░░░░░░░░░░░  0.08ms│
├─────────────────────────────────────────────────────────────┤
│ Total (p50)                                          0.76ms │
│ Total (p99)                                          1.50ms │
└─────────────────────────────────────────────────────────────┘

Memory Overhead:
- Base WASM runtime: 5-10MB
- Policy cache: 20-50MB (configurable)
- Compiled policies: 5-20MB
- Total per process: 30-80MB
```

---

## Option 3: Proxy/Gateway Pattern

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Infrastructure Layer                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    PolicyStack Gateway (Centralized)                      ││
│  │                                                                         ││
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────┐ ││
│  │  │  API Gateway  │  │  Envoy/Istio  │  │   Custom      │  │  Cache   │ ││
│  │  │  Integration  │  │  WASM Filter   │  │   Proxy       │  │  Layer   │ ││
│  │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └────┬─────┘ ││
│  │          │                  │                  │               │       ││
│  │          └──────────────────┴──────────────────┘               │       ││
│  │                             │                                   │       ││
│  │                             ▼                                   │       ││
│  │  ┌──────────────────────────────────────────────────────────┐ │       ││
│  │  │                 Policy Evaluation Engine                    │ │       ││
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │ │       ││
│  │  │  │  Rego    │  │  Cedar   │  │   ABAC   │  │   RBAC   │   │ │       ││
│  │  │  │  Eval    │  │  Eval    │  │   Eval   │  │   Eval   │   │ │       ││
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │ │       ││
│  │  └──────────────────────────────────────────────────────────┘ │       ││
│  │                             │                                  │       ││
│  │                             ▼                                  │       ││
│  │  ┌──────────────────────────────────────────────────────────┐ │       ││
│  │  │              Control Plane Connection                     │ │       ││
│  │  │         (Policy sync, metrics, audit log)                 │ │       ││
│  │  └──────────────────────────────────────────────────────────┘ │       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐              │
│         │                          │                          │              │
│         ▼                          ▼                          ▼              │
│  ┌───────────────┐        ┌───────────────┐        ┌───────────────┐        │
│  │  Service A    │        │  Service B    │        │  Service C    │        │
│  │               │        │               │        │               │        │
│  │ No policy code│        │ No policy code│        │ No policy code│        │
│  │ (zero trust)  │        │ (zero trust)  │        │ (zero trust)  │        │
│  └───────────────┘        └───────────────┘        └───────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Gateway Integration Patterns

#### Envoy Proxy External Authorization

```yaml
# Envoy configuration for external auth
static_resources:
  listeners:
    - address:
        socket_address:
          address: 0.0.0.0
          port_value: 8080
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: service_backend
                http_filters:
                  # PolicyStack external authorization
                  - name: envoy.ext_authz
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
                      grpc_service:
                        google_grpc:
                          target_uri: policystack-gateway:9090
                          stat_prefix: ext_authz
                        timeout: 0.5s
                      transport_api_version: V3
                      include_peer_certificate: true
                  
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
```

```rust
// PolicyStack gRPC authorization service
pub struct AuthorizationService {
    engine: Arc<PolicyEngine>,
    audit: Arc<AuditLogger>,
}

#[tonic::async_trait]
impl ExternalAuthorization for AuthorizationService {
    async fn check(
        &self,
        request: Request<CheckRequest>,
    ) -> Result<Response<CheckResponse>, Status> {
        let check_req = request.into_inner();
        
        // Convert Envoy attributes to PolicyStack request
        let attrs = check_req.attributes.as_ref().ok_or_else(|| {
            Status::invalid_argument("Missing attributes")
        })?;
        
        let policy_request = Request {
            subject: Subject::from_envoy_principal(&attrs.source)?,
            action: Action::from_envoy_method(&attrs.request)?,
            resource: Resource::from_envoy_path(&attrs.request)?,
            context: Context::from_envoy_attributes(attrs),
        };
        
        // Evaluate
        let start = Instant::now();
        let decision = self.engine.evaluate(policy_request.clone()).await
            .map_err(|e| Status::internal(e.to_string()))?;
        let duration = start.elapsed();
        
        // Audit log
        self.audit.log_decision(&policy_request, &decision, duration).await;
        
        // Build response
        let response = if decision.allow {
            CheckResponse {
                status: Some(HttpStatus { code: StatusCode::Ok as u32 }),
                ok_response: Some(OkHttpResponse {
                    headers: Self::build_headers(&decision),
                }),
                ..Default::default()
            }
        } else {
            CheckResponse {
                status: Some(HttpStatus { code: StatusCode::Forbidden as u32 }),
                denied_response: Some(DeniedHttpResponse {
                    status: Some(HttpStatus { code: StatusCode::Forbidden as u32 }),
                    body: format!("Access denied: {}", decision.reason),
                }),
                ..Default::default()
            }
        };
        
        Ok(Response::new(response))
    }
}
```

#### Kubernetes Admission Controller

```yaml
# PolicyStack as Kubernetes admission controller
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: policystack-admission
webhooks:
  - name: admission.policystack.io
    rules:
      - operations: ["CREATE", "UPDATE", "DELETE"]
        apiGroups: ["*"]
        apiVersions: ["*"]
        resources: ["*"]
    clientConfig:
      service:
        namespace: policystack
        name: admission-service
        path: /validate
      caBundle: ${CA_BUNDLE}
    admissionReviewVersions: ["v1", "v1beta1"]
    sideEffects: None
    timeoutSeconds: 5
    failurePolicy: Fail
```

### Gateway Pros

| Aspect | Assessment |
|--------|------------|
| **Zero Trust** | Services need no policy awareness |
| **Centralized Management** | Single point for policy distribution |
| **Consistent Enforcement** | Same policies across all services |
| **Service Simplicity** | Applications remain policy-agnostic |
| **Traffic Visibility** | Full observability at gateway layer |

### Gateway Cons

| Aspect | Assessment |
|--------|------------|
| **Latency** | Additional network hop (2-5ms) |
| **Availability** | Gateway becomes critical dependency |
| **Complexity** | Complex routing and failure handling |
| **Context Loss** | Limited access to application context |
| **Scale Challenges** | Gateway can become bottleneck |

### Gateway Performance Characteristics

```
Latency Breakdown (Gateway):
┌─────────────────────────────────────────────────────────────┐
│ Client to Gateway                ████████░░░░░░░░░░░░  1.0ms │
│ Gateway Processing               ████░░░░░░░░░░░░░░░░  0.5ms │
│ Policy Evaluation                ██████████████████   2.0ms │
│ Gateway to Service               ████████░░░░░░░░░░░░  1.0ms │
├─────────────────────────────────────────────────────────────┤
│ Total (p50)                                          4.5ms  │
│ Total (p99)                                          10.0ms │
└─────────────────────────────────────────────────────────────┘

Scalability:
- Single gateway instance: 10K-50K RPS
- Gateway cluster: 100K+ RPS with proper load balancing
- Cache hit ratio: 60-80% for repeated subjects
```

---

## Synchronous vs Asynchronous Evaluation

### Synchronous Evaluation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Synchronous Evaluation Flow                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Client ──► Gateway ──► Policy Evaluation ──► Service ──► Response          │
│              │                │                                           │
│              │                ▼                                           │
│              │         ┌──────────────┐                                   │
│              │         │  Eval Engine  │                                   │
│              │         │  • Rego       │                                   │
│              │         │  • Cedar      │                                   │
│              │         └──────────────┘                                   │
│              │                │                                           │
│              │                ▼ (blocking)                                │
│              └─────────► [Allow/Deny]                                     │
│                                                                              │
│  Characteristics:                                                           │
│  • Request blocks until decision made                                       │
│  • Strong consistency guarantees                                            │
│  • Higher latency (decision time)                                           │
│  • Simpler programming model                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Synchronous Implementation

```rust
// Synchronous evaluation (blocking)
pub async fn authorize_sync(
    &self,
    request: AuthzRequest,
) -> Result<AuthzDecision, AuthzError> {
    // Set timeout for synchronous evaluation
    let timeout = Duration::from_millis(100);
    
    match tokio::time::timeout(timeout, self.engine.evaluate(request)).await {
        Ok(Ok(decision)) => Ok(decision),
        Ok(Err(e)) => {
            // Evaluation error - fail closed
            tracing::error!("Policy evaluation failed: {}", e);
            Ok(AuthzDecision::deny("Policy evaluation error"))
        }
        Err(_) => {
            // Timeout - fail closed
            tracing::warn!("Policy evaluation timeout");
            Ok(AuthzDecision::deny("Policy evaluation timeout"))
        }
    }
}
```

### Asynchronous Evaluation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Asynchronous Evaluation Flow                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Request Flow:                                                              │
│  Client ──► Gateway ──► Local Cache Check ──► Service ──► Response          │
│                              │                                              │
│                              │ Cache Hit ──► Immediate Allow/Deny           │
│                              │                                              │
│                              │ Cache Miss ──► Async Evaluation              │
│                              │                     │                        │
│                              │                     ▼                        │
│                              │            ┌──────────────┐                 │
│                              │            │  Background   │                 │
│                              │            │  Eval Queue   │                 │
│                              │            └──────────────┘                 │
│                                                                              │
│  Update Flow:                                                               │
│  Background Eval ──► Cache Update ──► Audit Log                           │
│        │                                                                    │
│        └───► If decision changed, trigger re-evaluation/revocation          │
│                                                                              │
│  Characteristics:                                                           │
│  • Request doesn't block on policy evaluation                               │
│  • Eventual consistency (cache-based)                                       │
│  • Lower latency (cache lookup only)                                          │
│  • Requires cache warming and invalidation                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Asynchronous Implementation

```rust
// Asynchronous evaluation with cache
pub struct AsyncPolicyEvaluator {
    cache: Arc<Cache<String, AuthzDecision>>,
    eval_queue: mpsc::Sender<EvalTask>,
    background_worker: JoinHandle<()>,
}

impl AsyncPolicyEvaluator {
    pub async fn authorize_async(
        &self,
        request: AuthzRequest,
    ) -> Result<AuthzDecision, AuthzError> {
        let cache_key = request.cache_key();
        
        // Check cache first
        if let Some(decision) = self.cache.get(&cache_key).await {
            tracing::debug!("Cache hit for request {}", cache_key);
            return Ok(decision);
        }
        
        // Cache miss - return default and queue for evaluation
        let default_decision = self.default_decision(&request);
        
        // Queue background evaluation
        let _ = self.eval_queue.send(EvalTask {
            request,
            cache_key,
            callback: None,
        }).await;
        
        Ok(default_decision)
    }
    
    fn default_decision(&self, request: &AuthzRequest) -> AuthzDecision {
        // Conservative default based on request characteristics
        match request.sensitivity {
            Sensitivity::Critical => AuthzDecision::deny("Pending evaluation"),
            _ => AuthzDecision::allow_with_audit("Default allow pending eval"),
        }
    }
}

// Background evaluation worker
async fn background_evaluator(
    mut receiver: mpsc::Receiver<EvalTask>,
    engine: Arc<PolicyEngine>,
    cache: Arc<Cache<String, AuthzDecision>>,
) {
    while let Some(task) = receiver.recv().await {
        match engine.evaluate(task.request).await {
            Ok(decision) => {
                cache.insert(task.cache_key, decision.clone()).await;
                
                // Audit log the decision
                audit::log(&decision).await;
            }
            Err(e) => {
                tracing::error!("Background evaluation failed: {}", e);
            }
        }
    }
}
```

### Hybrid Approach

```rust
// Hybrid: Sync for critical, Async for non-critical
pub struct HybridPolicyEvaluator {
    sync_engine: Arc<PolicyEngine>,
    async_engine: Arc<AsyncPolicyEvaluator>,
    config: HybridConfig,
}

impl HybridPolicyEvaluator {
    pub async fn authorize(&self, request: AuthzRequest) -> Result<AuthzDecision, AuthzError> {
        // Route based on request characteristics
        if self.should_evaluate_sync(&request) {
            // Synchronous: Critical operations, high-confidence decisions
            self.sync_engine.evaluate(request).await
        } else {
            // Asynchronous: Non-critical, cache-friendly
            self.async_engine.authorize_async(request).await
        }
    }
    
    fn should_evaluate_sync(&self, request: &AuthzRequest) -> bool {
        match request.classification {
            // Always synchronous for financial transactions
            Classification::Financial => true,
            // Always synchronous for destructive operations
            Classification::Destructive => true,
            // Async acceptable for read operations
            Classification::ReadOnly => false,
            // Configurable for others
            _ => self.config.sync_for_unknown,
        }
    }
}
```

---

## Decision

### Selected: Multi-Modal Enforcement with Contextual Selection

**Primary Decision:** PolicyStack supports all three enforcement patterns, with automatic selection based on deployment context.

**Secondary Decision:** Synchronous evaluation as default, with asynchronous as opt-in optimization.

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PolicyStack Enforcement Architecture                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      Enforcement Router                                  ││
│  │                                                                        ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐││
│  │  │  Kubernetes  │  │   Docker     │  │   Serverless │  │   Edge     │││
│  │  │  Detected    │  │   Detected   │  │   Detected   │  │  Detected  │││
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘││
│  │         │                 │                 │                │       ││
│  │         ▼                 ▼                 ▼                ▼       ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ││
│  │  │   Sidecar    │  │   Sidecar    │  │   Library    │  │   Library  │  ││
│  │  │  (default)   │  │   (default)  │  │  (default)   │  │  (WASM)    │  ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  ││
│  │                                                                        ││
│  │  Override via configuration:                                           ││
│  │  enforcement.mode: sidecar | library | proxy | hybrid                  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      Evaluation Strategy                               ││
│  │                                                                        ││
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐      ││
│  │  │   Synchronous   │    │   Asynchronous  │    │     Hybrid      │      ││
│  │  │   (default)     │    │   (opt-in)      │    │   (configurable)│      ││
│  │  │                 │    │                 │    │                 │      ││
│  │  │ • Financial ops │    │ • Read-heavy    │    │ • Mixed workload│      ││
│  │  │ • Write ops     │    │ • Cacheable     │    │ • Dynamic select│      ││
│  │  │ • Critical path │    │ • Low latency   │    │ • Risk-based    │      ││
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘      ││
│  │                                                                        ││
│  │  Default timeout: 100ms (configurable)                                  ││
│  │  Failure mode: Closed (deny)                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Deployment Matrix

| Environment | Default Pattern | Rationale |
|-------------|-----------------|-----------|
| Kubernetes | Sidecar | Industry standard, Istio/Envoy integration |
| Docker Compose | Sidecar | Consistency with production |
| AWS Lambda | Library (WASM) | Cold start sensitivity, resource constraints |
| Cloudflare Workers | Library (WASM) | Edge deployment, V8 isolate compatibility |
| EC2/VMs | Configurable | Customer preference |
| Service Mesh | Proxy | Centralized, zero-trust architecture |

### Configuration

```yaml
# PolicyStack enforcement configuration
enforcement:
  # Auto-detect or explicit selection
  mode: auto  # auto | sidecar | library | proxy | hybrid
  
  # When mode: auto, detection order
  auto_detection:
    - kubernetes_sidecar
    - service_mesh_proxy
    - serverless_library
    - container_sidecar
  
  # Evaluation strategy
  evaluation:
    default: synchronous
    async_threshold: 50ms  # Use async if sync takes longer
    
    sync_config:
      timeout_ms: 100
      retry_count: 2
      fail_open: false  # Always fail closed
      
    async_config:
      cache_ttl_seconds: 300
      default_decision: deny  # Conservative default
      max_queue_depth: 10000
      
  # Sidecar specific
  sidecar:
    image: policystack/sidecar:v1.0
    resources:
      memory: "64Mi"
      cpu: "100m"
    port: 8181
    protocol: grpc
    
  # Library specific
  library:
    wasm_module: policystack-engine.wasm
    cache_size: 10000
    update_interval_seconds: 30
    
  # Proxy specific
  proxy:
    gateway_endpoint: http://policystack-gateway:8080
    timeout_ms: 200
    cache_enabled: true
```

---

## Consequences

### Positive

1. **Flexibility:** Supports diverse deployment scenarios without vendor lock-in
2. **Performance Optimization:** Choose pattern based on latency requirements
3. **Gradual Migration:** Start with sidecar, migrate to library if needed
4. **Risk Distribution:** No single point of failure across all deployments
5. **Ecosystem Compatibility:** Works with existing infrastructure (Istio, Envoy, etc.)

### Negative

1. **Complexity:** More code paths to maintain and test
2. **Documentation:** Must document multiple deployment patterns
3. **Testing Matrix:** Combinatorial explosion of (pattern × engine × environment)
4. **Support Burden:** Users may choose inappropriate patterns
5. **Feature Parity:** Some features may not work in all modes

### Mitigations

| Risk | Mitigation |
|------|------------|
| Complexity | Abstract common logic; shared test suite |
| Documentation | Decision matrix and deployment guides |
| Testing | CI runs all patterns; integration test matrix |
| Support | Auto-detection with override warnings |
| Feature Parity | Clear capability matrix per pattern |

---

## Implementation Phases

### Phase 1: Sidecar Foundation (MVP)

```rust
// Sidecar implementation
pub struct SidecarServer {
    engine: Arc<PolicyEngine>,
    config: SidecarConfig,
}

#[tonic::async_trait]
impl PolicyService for SidecarServer {
    async fn evaluate(
        &self,
        request: Request<EvalRequest>,
    ) -> Result<Response<EvalResponse>, Status> {
        let req = request.into_inner();
        
        let decision = self.engine.evaluate(Request::from_proto(req)?)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        
        Ok(Response::new(EvalResponse::from(decision)))
    }
}
```

### Phase 2: Library SDKs

- Rust: Native crate
- Go: CGO bindings
- Node.js: WASM + N-API
- Python: WASM + PyO3
- Java: JNI + WASM

### Phase 3: Gateway Integration

- Envoy WASM filter
- Istio integration
- NGINX module
- Kong plugin

### Phase 4: Hybrid Intelligence

- Dynamic pattern selection
- Performance-based routing
- Automatic fallback

---

## Related Decisions

- **ADR-001:** Policy Language Selection - Determines what policies are evaluated
- **ADR-003:** Audit Strategy - How enforcement events are logged
- **ADR-004:** Control Plane Architecture - Policy distribution to enforcement points

---

## References

1. Istio Security Architecture: https://istio.io/latest/docs/concepts/security/
2. Envoy External Authorization: https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/ext_authz_filter
3. Kubernetes Sidecar Pattern: https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/
4. Open Policy Agent Deployment: https://www.openpolicyagent.org/docs/latest/deployments/
5. AWS Lambda Extensions: https://docs.aws.amazon.com/lambda/latest/dg/runtimes-extensions-api.html

---

**Status:** Proposed  
**Date:** 2026-04-02  
**Next Review:** 2026-05-02

*End of ADR-002*

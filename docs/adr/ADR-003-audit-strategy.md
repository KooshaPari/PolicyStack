# ADR-003: Audit Strategy

**Status:** Proposed  
**Date:** 2026-04-02  
**Authors:** PolicyStack Architecture Team  
**Reviewers:** Engineering Leadership, Security Team, Compliance Team, Legal

---

## Context

Policy decisions often require comprehensive audit trails for compliance, forensics, and operational analysis. This ADR establishes PolicyStack's approach to audit logging, including:

1. **What to log** - Decision events, context, and metadata
2. **When to log** - Synchronous vs asynchronous logging strategies
3. **Where to store** - Storage backends and retention policies
4. **How to query** - Search, aggregation, and analysis capabilities
5. **Compliance mapping** - Regulatory requirements (SOX, PCI-DSS, HIPAA, GDPR)

The audit system must balance comprehensiveness with performance, ensuring that logging doesn't materially impact authorization latency while maintaining complete decision records.

---

## Decision Drivers

| Driver | Weight | Description |
|--------|--------|-------------|
| **Compliance** | 25% | SOX, PCI-DSS, HIPAA, GDPR, SOC 2 requirements |
| **Forensics** | 20% | Incident investigation capability |
| **Performance** | 20% | Minimal impact on authorization path |
| **Storage Cost** | 15% | Efficient storage and retention |
| **Query Performance** | 15% | Fast search and aggregation |
| **Reliability** | 5% | Guaranteed delivery, no loss |

---

## Audit Event Model

### Core Event Schema

```protobuf
// policystack_audit.proto
syntax = "proto3";
package policystack.audit;

import "google/protobuf/timestamp.proto";
import "google/protobuf/struct.proto";

message AuditEvent {
  // Identifiers
  string event_id = 1;           // UUID v4
  string trace_id = 2;           // Distributed tracing
  string span_id = 3;            // Span within trace
  string parent_span_id = 4;     // Parent span (for nested evals)
  
  // Timing
  google.protobuf.Timestamp timestamp = 5;
  int64 duration_micros = 6;       // Evaluation duration
  
  // Subject (who)
  Subject subject = 7;
  
  // Action (what)
  Action action = 8;
  
  // Resource (on what)
  Resource resource = 9;
  
  // Context (environment)
  Context context = 10;
  
  // Decision outcome
  Decision decision = 11;
  
  // Policy metadata
  PolicyInfo policy = 12;
  
  // Enforcement metadata
  EnforcementInfo enforcement = 13;
  
  // Compliance tags
  ComplianceInfo compliance = 14;
  
  // Extensions
  google.protobuf.Struct metadata = 15;
}

message Subject {
  string id = 1;
  string type = 2;               // user, service, device
  repeated string roles = 3;
  map<string, string> attributes = 4;
  AuthenticationInfo auth = 5;
}

message AuthenticationInfo {
  string method = 1;             // mfa, sso, api_key, certificate
  string provider = 2;           // auth0, okta, custom
  google.protobuf.Timestamp authenticated_at = 3;
  string session_id = 4;
}

message Action {
  string type = 1;                 // read, write, delete, execute
  string resource_type = 2;
  map<string, string> attributes = 3;
}

message Resource {
  string id = 1;
  string type = 2;
  string owner = 3;
  map<string, string> attributes = 4;
  repeated string tags = 5;
  string sensitivity = 6;          // low, medium, high, critical
}

message Context {
  google.protobuf.Timestamp request_time = 1;
  string source_ip = 2;
  string user_agent = 3;
  string location = 4;
  DeviceInfo device = 5;
  RiskInfo risk = 6;
  map<string, string> headers = 7;
  map<string, string> environment = 8;
}

message DeviceInfo {
  string id = 1;
  string type = 2;
  bool trusted = 3;
  string posture = 4;
}

message RiskInfo {
  float score = 1;
  repeated string factors = 2;
  string level = 3;              // low, medium, high, critical
}

message Decision {
  string result = 1;             // allow, deny, error, indeterminate
  string reason = 2;
  repeated string reasons = 3;   // Detailed reason list
  string advice = 4;             // Suggested remediation
  map<string, string> obligations = 5;  // Actions to take
}

message PolicyInfo {
  string policy_id = 1;
  string policy_version = 2;
  string engine = 3;               // rego, cedar
  repeated string rules_evaluated = 4;
  repeated string rules_matched = 5;
  google.protobuf.Struct trace = 6;
}

message EnforcementInfo {
  string mode = 1;               // sidecar, library, proxy
  string node_id = 2;
  string service_name = 3;
  string service_version = 4;
}

message ComplianceInfo {
  repeated string frameworks = 1;  // sox, pci, hipaa, gdpr
  map<string, string> tags = 2;
  int64 retention_days = 3;
  bool sensitive = 4;
}
```

### Event Classification

```rust
// Audit event classification for retention and routing
pub enum EventClassification {
    // Compliance-critical: 7+ year retention, immutable storage
    FinancialTransaction,
    HealthcareAccess,
    
    // Security-critical: 3+ year retention
    AdminAction,
    PrivilegedAccess,
    FailedAuthentication,
    
    // Operational: 1 year retention
    StandardAccess,
    PolicyChange,
    
    // Debug: 30 day retention
    TestEvent,
    DebugTrace,
}

impl EventClassification {
    pub fn retention_days(&self) -> u64 {
        match self {
            EventClassification::FinancialTransaction => 2555,  // 7 years
            EventClassification::HealthcareAccess => 2555,
            EventClassification::AdminAction => 1095,         // 3 years
            EventClassification::PrivilegedAccess => 1095,
            EventClassification::FailedAuthentication => 1095,
            EventClassification::StandardAccess => 365,
            EventClassification::PolicyChange => 365,
            EventClassification::TestEvent => 30,
            EventClassification::DebugTrace => 30,
        }
    }
    
    pub fn storage_tier(&self) -> StorageTier {
        match self {
            EventClassification::FinancialTransaction => StorageTier::Immutable,
            EventClassification::HealthcareAccess => StorageTier::Immutable,
            EventClassification::AdminAction => StorageTier::Standard,
            EventClassification::PrivilegedAccess => StorageTier::Standard,
            EventClassification::FailedAuthentication => StorageTier::Standard,
            EventClassification::StandardAccess => StorageTier::Standard,
            EventClassification::PolicyChange => StorageTier::Standard,
            EventClassification::TestEvent => StorageTier::Cold,
            EventClassification::DebugTrace => StorageTier::Cold,
        }
    }
}
```

---

## Storage Architecture

### Tiered Storage Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Audit Storage Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         Hot Tier (24 hours)                            ││
│  │  ┌─────────────────────────────────────────────────────────────────┐   ││
│  │  │  In-Memory Ring Buffer (per node)                                │   ││
│  │  │  • Capacity: 100K events per node                                │   ││
│  │  │  • Queryable via local API                                       │   ││
│  │  │  • Used for: Real-time alerting, recent event lookup             │   ││
│  │  └─────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                       Warm Tier (90 days)                              ││
│  │  ┌─────────────────────────────────────────────────────────────────┐   ││
│  │  │  Time-Series Database (TimescaleDB/ClickHouse)                   │   ││
│  │  │  • Partitioned by day                                            │   ││
│  │  │  • Indexed: time, subject, resource, decision                    │   ││
│  │  │  • Queryable via SQL API                                         │   ││
│  │  │  • Used for: Operational queries, dashboards, investigations     │   ││
│  │  └─────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                       Cold Tier (Retention period)                     ││
│  │  ┌─────────────────────────────────────────────────────────────────┐   ││
│  │  │  Object Storage (S3/GCS/Azure Blob) + Parquet                   │   ││
│  │  │  • Compressed, columnar format                                   │   ││
│  │  │  • Partitioned: year/month/day                                   │   ││
│  │  │  • Queryable via Athena/BigQuery/Spark                           │   ││
│  │  │  • Used for: Compliance queries, long-term analytics             │   ││
│  │  └─────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     Immutable Tier (Compliance)                          ││
│  │  ┌─────────────────────────────────────────────────────────────────┐   ││
│  │  │  WORM Storage (S3 Glacier Lock / Azure Immutable Blob)          │   ││
│  │  │  • Write-Once-Read-Many                                          │   ││
│  │  │  • Cryptographic verification (Merkle tree)                      │   ││
│  │  │  • Used for: SOX, PCI-DSS, legal hold                           │   ││
│  │  └─────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Hot Tier Implementation

```rust
// In-memory ring buffer for recent events
pub struct HotBuffer {
    buffer: Arc<RwLock<RingBuffer<AuditEvent>>>,
    subscribers: Arc<RwLock<Vec<mpsc::Sender<AuditEvent>>>>,
}

impl HotBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            buffer: Arc::new(RwLock::new(RingBuffer::with_capacity(capacity))),
            subscribers: Arc::new(RwLock::new(Vec::new())),
        }
    }
    
    pub async fn write(&self, event: AuditEvent) {
        // Write to buffer
        {
            let mut buf = self.buffer.write().await;
            buf.push(event.clone());
        }
        
        // Notify subscribers (for real-time alerting)
        let subs = self.subscribers.read().await;
        for sub in subs.iter() {
            let _ = sub.try_send(event.clone());
        }
    }
    
    pub async fn query_recent(
        &self,
        duration: Duration,
        filter: AuditFilter,
    ) -> Vec<AuditEvent> {
        let buf = self.buffer.read().await;
        let cutoff = Utc::now() - duration;
        
        buf.iter()
            .filter(|e| e.timestamp > cutoff)
            .filter(|e| filter.matches(e))
            .cloned()
            .collect()
    }
}
```

### Warm Tier Implementation

```sql
-- TimescaleDB schema for warm tier
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Main events table
CREATE TABLE audit_events (
    event_id UUID PRIMARY KEY,
    trace_id UUID,
    timestamp TIMESTAMPTZ NOT NULL,
    duration_micros BIGINT,
    
    -- Subject
    subject_id TEXT,
    subject_type TEXT,
    subject_roles TEXT[],
    
    -- Action
    action_type TEXT,
    resource_type TEXT,
    
    -- Resource
    resource_id TEXT,
    resource_owner TEXT,
    resource_sensitivity TEXT,
    
    -- Decision
    decision_result TEXT,
    decision_reason TEXT,
    
    -- Policy
    policy_id TEXT,
    policy_version TEXT,
    policy_engine TEXT,
    
    -- Enforcement
    enforcement_mode TEXT,
    node_id TEXT,
    service_name TEXT,
    
    -- Compliance
    compliance_frameworks TEXT[],
    retention_days INT,
    is_sensitive BOOLEAN,
    
    -- Raw event (compressed JSONB)
    raw_event JSONB
);

-- Convert to hypertable (time-series partitioning)
SELECT create_hypertable('audit_events', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- Indexes for common queries
CREATE INDEX idx_audit_subject ON audit_events (subject_id, timestamp DESC);
CREATE INDEX idx_audit_resource ON audit_events (resource_id, timestamp DESC);
CREATE INDEX idx_audit_decision ON audit_events (decision_result, timestamp DESC);
CREATE INDEX idx_audit_service ON audit_events (service_name, timestamp DESC);
CREATE INDEX idx_audit_trace ON audit_events (trace_id);
CREATE INDEX idx_audit_compliance ON audit_events (compliance_frameworks, timestamp DESC);

-- Compression policy (compress after 7 days)
ALTER TABLE audit_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'service_name, decision_result'
);

SELECT add_compression_policy('audit_events', INTERVAL '7 days');

-- Retention policy (drop after retention period)
SELECT add_retention_policy('audit_events', INTERVAL '90 days');
```

### Cold Tier Implementation

```python
# Parquet schema for cold storage
import pyarrow as pa
from pyarrow import parquet as pq

audit_schema = pa.schema([
    ('event_id', pa.string()),
    ('trace_id', pa.string()),
    ('timestamp', pa.timestamp('us')),
    ('duration_micros', pa.int64()),
    ('subject_id', pa.string()),
    ('subject_type', pa.string()),
    ('subject_roles', pa.list_(pa.string())),
    ('action_type', pa.string()),
    ('resource_id', pa.string()),
    ('resource_type', pa.string()),
    ('resource_sensitivity', pa.string()),
    ('decision_result', pa.string()),
    ('decision_reason', pa.string()),
    ('policy_id', pa.string()),
    ('policy_engine', pa.string()),
    ('service_name', pa.string()),
    ('compliance_frameworks', pa.list_(pa.string())),
    ('year', pa.int32()),      # Partition column
    ('month', pa.int32()),     # Partition column
    ('day', pa.int32()),       # Partition column
])

def write_to_cold_tier(events: list[dict], s3_bucket: str):
    """Write events to S3 as Parquet, partitioned by date."""
    import pandas as pd
    
    df = pd.DataFrame(events)
    
    # Add partition columns
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month
    df['day'] = df['timestamp'].dt.day
    
    # Write partitioned Parquet
    pq.write_to_dataset(
        table=pa.Table.from_pandas(df, schema=audit_schema),
        root_path=f's3://{s3_bucket}/audit-events/',
        partition_cols=['year', 'month', 'day'],
        compression='zstd',
    )
```

### Immutable Tier Implementation

```yaml
# S3 Object Lock configuration for immutable storage
immutable_storage:
  bucket: policystack-audit-immutable
  
  # WORM configuration
  object_lock:
    enabled: true
    mode: COMPLIANCE  # or GOVERNANCE
    retention:
      days: 2555  # 7 years minimum
      
  # Additional protection
  versioning:
    enabled: true
    mfa_delete: true
    
  # Encryption
  encryption:
    algorithm: AES256
    kms_key_id: alias/policystack-audit
    
  # Cross-region replication for durability
  replication:
    enabled: true
    destination_bucket: policystack-audit-immutable-dr
    
  # Integrity verification
  integrity:
    checksum_algorithm: SHA256
    merkle_tree_enabled: true
    verification_frequency: daily
```

---

## Collection Strategies

### Strategy 1: Inline (Synchronous)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Inline Audit Collection                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Request ──► Policy Evaluation ──► Audit Log ──► Response                   │
│                        │          (blocking)                                │
│                        ▼                                                   │
│              ┌───────────────────┐                                         │
│              │  Local Buffer     │                                         │
│              │  (non-blocking)   │                                         │
│              └─────────┬─────────┘                                         │
│                        │                                                   │
│                        ▼                                                   │
│              ┌───────────────────┐                                         │
│              │  Async Flush      │                                         │
│              │  to Storage       │                                         │
│              └───────────────────┘                                         │
│                                                                              │
│  Latency impact: 0.1-0.5ms (buffer write only)                             │
│  Durability: Eventual (buffer flush)                                       │
│  Use case: Standard access events                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```rust
// Inline audit collection
pub struct InlineAuditCollector {
    buffer: Arc<tokio::sync::RwLock<Vec<AuditEvent>>>,
    flush_interval: Duration,
    max_buffer_size: usize,
}

impl InlineAuditCollector {
    pub async fn log(&self, event: AuditEvent) {
        // Fast in-memory append
        let mut buf = self.buffer.write().await;
        buf.push(event);
        
        // Trigger async flush if buffer full
        if buf.len() >= self.max_buffer_size {
            drop(buf);  // Release lock
            self.flush().await;
        }
    }
    
    async fn flush(&self) {
        let events = {
            let mut buf = self.buffer.write().await;
            std::mem::take(&mut *buf)
        };
        
        // Spawn background flush
        tokio::spawn(async move {
            if let Err(e) = self.storage.write_batch(events).await {
                tracing::error!("Audit flush failed: {}", e);
                // Retry with backoff
            }
        });
    }
}
```

### Strategy 2: Out-of-Band (Asynchronous)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Out-of-Band Audit Collection                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Request ──► Policy Evaluation ──┬──► Response                             │
│                        │         │                                         │
│                        │         │ (no blocking)                            │
│                        ▼         │                                         │
│              ┌──────────────────┴──┐                                      │
│              │   Event Channel     │                                      │
│              │   (bounded queue)   │                                      │
│              └──────────┬───────────┘                                      │
│                         │                                                  │
│                         ▼                                                  │
│              ┌───────────────────┐                                        │
│              │  Background Worker │                                        │
│              │  (batched writes) │                                        │
│              └───────────────────┘                                        │
│                                                                              │
│  Latency impact: <0.01ms (channel send)                                    │
│  Durability: Eventual (queued)                                             │
│  Use case: High-throughput scenarios                                       │
│  Risk: Queue overflow on backpressure                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```rust
// Out-of-band audit collection
pub struct OutOfBandAuditCollector {
    sender: mpsc::Sender<AuditEvent>,
    dropped_count: AtomicU64,
}

impl OutOfBandAuditCollector {
    pub fn new(buffer_size: usize, storage: Arc<dyn AuditStorage>) -> Self {
        let (tx, mut rx) = mpsc::channel(buffer_size);
        
        // Spawn background worker
        tokio::spawn(async move {
            let mut batch = Vec::with_capacity(100);
            
            loop {
                match tokio::time::timeout(
                    Duration::from_secs(1),
                    rx.recv()
                ).await {
                    Ok(Some(event)) => {
                        batch.push(event);
                        
                        if batch.len() >= 100 {
                            storage.write_batch(std::mem::take(&mut batch)).await;
                        }
                    }
                    Ok(None) => break,  // Channel closed
                    Err(_) => {
                        // Timeout - flush partial batch
                        if !batch.is_empty() {
                            storage.write_batch(std::mem::take(&mut batch)).await;
                        }
                    }
                }
            }
        });
        
        Self {
            sender: tx,
            dropped_count: AtomicU64::new(0),
        }
    }
    
    pub fn log(&self, event: AuditEvent) {
        // Non-blocking send
        match self.sender.try_send(event) {
            Ok(_) => {}
            Err(mpsc::error::TrySendError::Full(_)) => {
                self.dropped_count.fetch_add(1, Ordering::Relaxed);
                tracing::warn!("Audit queue full, event dropped");
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {
                tracing::error!("Audit channel closed");
            }
        }
    }
}
```

### Strategy 3: Guaranteed Delivery

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Guaranteed Delivery Audit Collection                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Request ──► Policy Evaluation ──► Local WAL ──► Response                 │
│                        │              │  │                                  │
│                        │              │  └── Ack (durability)              │
│                        │              │                                     │
│                        │              ▼                                     │
│                        │         ┌──────────────┐                          │
│                        │         │  Write-Ahead │                          │
│                        │         │  Log (disk)  │                          │
│                        │         └──────┬───────┘                          │
│                        │                │                                  │
│                        ▼                ▼                                  │
│                   Response (only after WAL sync)                            │
│                                                                              │
│  Latency impact: 1-5ms (fsync)                                              │
│  Durability: Guaranteed (disk persistence)                                  │
│  Use case: Financial transactions, compliance-critical events              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```rust
// Guaranteed delivery with WAL
pub struct GuaranteedAuditCollector {
    wal: Arc<WriteAheadLog>,
    storage: Arc<dyn AuditStorage>,
}

impl GuaranteedAuditCollector {
    pub async fn log(&self, event: AuditEvent) -> Result<(), AuditError> {
        // Serialize event
        let bytes = event.serialize()?;
        
        // Write to WAL with fsync
        let entry_id = self.wal.append_and_sync(bytes).await?;
        
        // Now safe to respond to client
        Ok(())
    }
    
    // Background replication to remote storage
    async fn replication_worker(&self) {
        let mut reader = self.wal.reader();
        
        loop {
            match reader.read_batch(100).await {
                Ok(entries) if !entries.is_empty() => {
                    let events: Vec<AuditEvent> = entries
                        .iter()
                        .map(|e| AuditEvent::deserialize(&e.data))
                        .collect::<Result<Vec<_>, _>>()?;
                    
                    match self.storage.write_batch(events).await {
                        Ok(_) => {
                            // Truncate WAL up to this point
                            reader.ack(entries.last().unwrap().id);
                        }
                        Err(e) => {
                            tracing::error!("Storage write failed: {}", e);
                            tokio::time::sleep(Duration::from_secs(1)).await;
                        }
                    }
                }
                _ => {
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
            }
        }
    }
}
```

### Strategy Selection Matrix

| Event Type | Strategy | Latency | Durability |
|------------|----------|---------|------------|
| Financial transactions | Guaranteed | 1-5ms | Disk + WAL |
| Healthcare records | Guaranteed | 1-5ms | Disk + WAL |
| Admin actions | Inline | 0.1-0.5ms | Memory + async |
| Standard access | Out-of-band | <0.01ms | Memory + queued |
| Debug traces | Out-of-band | <0.01ms | Optional |

---

## Query and Analysis

### Real-Time Alerting

```yaml
# Alerting rules configuration
audit_alerts:
  - name: privilege_escalation_attempt
    condition: |
      decision_result = 'deny' 
      AND action_type = 'grant'
      AND subject_roles contains 'admin'
    severity: critical
    channels: [pagerduty, slack]
    
  - name: unusual_access_pattern
    condition: |
      decision_result = 'allow'
      AND resource_sensitivity = 'critical'
      AND source_country not in subject.normal_countries
    severity: high
    channels: [slack, email]
    
  - name: policy_evaluation_spike
    condition: |
      rate(audit_events[5m]) > 10000/s
    severity: warning
    channels: [slack]
    
  - name: compliance_violation
    condition: |
      decision_result = 'allow'
      AND compliance_frameworks contains 'sox'
      AND policy_engine = 'fallback'
    severity: critical
    channels: [pagerduty, jira]
```

### Forensic Query Interface

```rust
// Forensic query capabilities
pub struct AuditQuery {
    // Time range
    pub start: DateTime<Utc>,
    pub end: DateTime<Utc>,
    
    // Filters
    pub subject_id: Option<String>,
    pub resource_id: Option<String>,
    pub decision_result: Option<String>,
    pub service_name: Option<String>,
    
    // Full-text search
    pub full_text: Option<String>,
    
    // Aggregation
    pub group_by: Vec<String>,
    pub aggregations: Vec<Aggregation>,
}

pub async fn forensic_query(
    &self,
    query: AuditQuery,
) -> Result<QueryResult, QueryError> {
    // Route to appropriate tier based on time range
    let tier = self.select_tier(&query);
    
    match tier {
        StorageTier::Hot => self.hot_buffer.query(query).await,
        StorageTier::Warm => self.timeseries_db.query(query).await,
        StorageTier::Cold => self.query_cold_storage(query).await,
        StorageTier::Immutable => self.query_immutable_storage(query).await,
    }
}
```

### Compliance Reporting

```sql
-- SOX compliance report: Who accessed financial data
SELECT 
    date_trunc('day', timestamp) as day,
    subject_id,
    subject_roles,
    count(*) as access_count,
    array_agg(DISTINCT resource_id) as resources_accessed
FROM audit_events
WHERE 
    compliance_frameworks @> ARRAY['sox']
    AND timestamp >= now() - interval '90 days'
    AND decision_result = 'allow'
GROUP BY 1, 2, 3
ORDER BY access_count DESC;

-- PCI-DSS: Failed authentication attempts
SELECT 
    subject_id,
    source_ip,
    count(*) as failed_attempts,
    min(timestamp) as first_attempt,
    max(timestamp) as last_attempt
FROM audit_events
WHERE 
    compliance_frameworks @> ARRAY['pci']
    AND decision_result = 'deny'
    AND action_type = 'authenticate'
    AND timestamp >= now() - interval '24 hours'
GROUP BY 1, 2
HAVING count(*) > 5;

-- GDPR: Data subject access audit
SELECT 
    subject_id,
    action_type,
    resource_type,
    decision_result,
    timestamp
FROM audit_events
WHERE 
    subject_id = 'user:data-subject-123'
    AND timestamp >= now() - interval '3 years'
ORDER BY timestamp DESC;
```

---

## Retention and Lifecycle

### Automated Retention Policies

```rust
// Retention policy engine
pub struct RetentionEngine {
    policies: Vec<RetentionPolicy>,
    scheduler: JobScheduler,
}

impl RetentionEngine {
    pub async fn apply_retention(&self) -> Result<(), RetentionError> {
        for policy in &self.policies {
            match policy.action {
                RetentionAction::Delete => {
                    self.storage.delete_before(policy.cutoff_date).await?;
                }
                RetentionAction::Archive => {
                    let events = self.storage.query_before(policy.cutoff_date).await?;
                    self.cold_storage.archive(events).await?;
                    self.storage.delete_before(policy.cutoff_date).await?;
                }
                RetentionAction::Compress => {
                    self.storage.compress_older_than(policy.cutoff_date).await?;
                }
                RetentionAction::LegalHold => {
                    // Skip deletion if legal hold active
                    if !self.legal_hold_active().await {
                        self.storage.delete_before(policy.cutoff_date).await?;
                    }
                }
            }
        }
        
        Ok(())
    }
}

// Default retention policies
impl Default for RetentionEngine {
    fn default() -> Self {
        let policies = vec![
            // Debug traces: 30 days then delete
            RetentionPolicy {
                event_class: EventClassification::DebugTrace,
                retention: Duration::days(30),
                action: RetentionAction::Delete,
            },
            // Standard access: 1 year then archive
            RetentionPolicy {
                event_class: EventClassification::StandardAccess,
                retention: Duration::days(365),
                action: RetentionAction::Archive,
            },
            // Financial: 7 years then immutable storage
            RetentionPolicy {
                event_class: EventClassification::FinancialTransaction,
                retention: Duration::days(2555),
                action: RetentionAction::LegalHold,
            },
        ];
        
        Self {
            policies,
            scheduler: JobScheduler::new(),
        }
    }
}
```

### Legal Hold Management

```yaml
# Legal hold configuration
legal_holds:
  hold_001:
    case_id: "litigation-2024-001"
    description: "Quarterly earnings investigation"
    created_by: "legal@company.com"
    created_at: "2024-01-15T00:00:00Z"
    
    // Events matching these criteria cannot be deleted
    scope:
      subjects: ["user:exec-001", "user:exec-002"]
      date_range:
        start: "2023-01-01T00:00:00Z"
        end: "2023-12-31T23:59:59Z"
      resource_types: ["financial_report", "earnings_data"]
      
    // Hold prevents deletion of matching events
    action: prevent_deletion
    
    // Notification on hold application
    notifications:
      - legal@company.com
      - compliance@company.com
```

---

## Decision

### Selected: Tiered Storage with Contextual Collection

**Primary Decision:** Implement four-tier storage with automatic tiering based on event age and classification.

**Secondary Decision:** Support all three collection strategies with automatic selection based on event criticality.

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PolicyStack Audit Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Collection:                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │ Guaranteed  │  │   Inline    │  │ Out-of-Band │                         │
│  │   (WAL)     │  │  (memory)   │  │   (queue)   │                         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                         │
│         │                │                │                                │
│         └────────────────┴────────────────┘                                │
│                          │                                                   │
│                          ▼                                                   │
│  Storage:                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │   Hot    │───►│   Warm   │───►│   Cold   │───►│Immutable │              │
│  │(24 hours)│    │(90 days) │    │(1 year)  │    │(7 years) │              │
│  │  Memory  │    │  Timescale│   │  Parquet │   │   WORM   │              │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│                                                                              │
│  Query:                                                                     │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │  Unified Query API (SQL-like)                            │              │
│  │  • Automatic tier routing                                │              │
│  │  • Cross-tier aggregation                                │              │
│  │  • Compliance report templates                           │              │
│  └──────────────────────────────────────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Consequences

### Positive

1. **Compliance Ready:** Meets SOX, PCI-DSS, HIPAA, GDPR requirements
2. **Cost Optimized:** Tiered storage reduces costs (hot:expensive → cold:cheap)
3. **Performance Preserved:** Out-of-band collection minimizes latency
4. **Forensic Capability:** Full search and correlation across all tiers
5. **Reliability:** Guaranteed delivery for critical events

### Negative

1. **Complexity:** Four storage tiers to manage and monitor
2. **Operational Burden:** Retention policies require ongoing management
3. **Query Complexity:** Cross-tier queries may be slower
4. **Storage Cost:** Comprehensive logging requires significant storage
5. **Privacy Risk:** Centralized audit logs become high-value target

### Mitigations

| Risk | Mitigation |
|------|------------|
| Complexity | Automated tiering, unified API |
| Operational | Policy-as-code for retention |
| Query Speed | Pre-aggregated summaries, indexes |
| Storage Cost | Compression, lifecycle policies |
| Privacy Risk | Encryption, access controls, masking |

---

## Implementation Phases

### Phase 1: Core Schema and Hot Tier

- Define protobuf schema
- Implement in-memory ring buffer
- Basic SQL query interface

### Phase 2: Warm and Cold Tiers

- TimescaleDB integration
- Parquet export to S3
- Automated tiering logic

### Phase 3: Compliance Features

- Immutable storage (WORM)
- Legal hold management
- Compliance report templates

### Phase 4: Advanced Analytics

- Real-time alerting
- Anomaly detection
- Machine learning on audit patterns

---

## Related Decisions

- **ADR-001:** Policy Language Selection - Determines what policies generate audit events
- **ADR-002:** Enforcement Pattern - Affects where audit collection happens
- **ADR-004:** Data Model - Defines subject, resource, and context schemas

---

## References

1. PCI-DSS Requirement 10: https://www.pcisecuritystandards.org/document_library
2. HIPAA Audit Controls: https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html
3. SOX Section 404: https://www.sec.gov/info/rules/final/33-8238.htm
4. GDPR Article 30: https://gdpr.eu/article-30-records-of-processing/
5. TimescaleDB Documentation: https://docs.timescale.com/
6. AWS S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

---

**Status:** Proposed  
**Date:** 2026-04-02  
**Next Review:** 2026-05-02

*End of ADR-003*

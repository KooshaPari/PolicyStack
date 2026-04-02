---
layout: doc
title: User Journeys
---

# PolicyStack User Journeys

> Visual workflows for PolicyStack

## Quick Navigation

| Journey | Time | Complexity | Status |
|---------|------|------------|--------|
| [Quick Start](./quick-start) | 5 min | ⭐ Beginner | ✅ Ready |
| [Core Integration](./core-integration) | 15 min | ⭐⭐ Intermediate | 📋 Planned |
| [Production Setup](./production-setup) | 30 min | ⭐⭐⭐ Advanced | 📋 Planned |

## Architecture

```mermaid
flowchart TB
    A[Input] --> B[Processing]
    B --> C[Output]
```

## Performance

| Metric | P50 | P95 |
|--------|-----|-----|
| Cold Start | < 10ms | < 50ms |
| Hot Path | < 1ms | < 5ms |

---
status: todo
service: shared
type: feature
ticket_id: TKT-003
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/shared_pydantic_models.md
pr:
  url: ""
  branch: ""
tasks:
  - "Define entity models (Trend, Theme, ContentOption, Post)"
  - "Define status enums (ContentStatus, PostStatus)"
  - "Define API request/response models"
  - "Build record-to-model helper functions"
  - "Write model validation tests"
history: []
comments: []
---

# [TKT-003] Shared Pydantic Models

## Description
Define all shared data models using Pydantic v2 for type-safe data exchange between modules. Includes entity models, status enums, API request/response models, and database record helpers.

## Dependencies
- **Blocks**: TKT-006, TKT-007, TKT-008, TKT-009, TKT-010, TKT-011
- **Blocked by**: TKT-002

## Technical Specification
See [docs/technical/shared_pydantic_models.md](docs/technical/shared_pydantic_models.md)

## Tasks
1. Define `Trend`, `Theme`, `ContentOption`, `Post` Pydantic models with field validation
2. Define `ContentStatus` and `PostStatus` enums
3. Define API models: `ContentOptionResponse`, `PostResponse`, `HealthResponse`
4. Build `*_from_record()` helper functions for asyncpg Record conversion
5. Write tests: valid/invalid data, serialization round-trip, enum values

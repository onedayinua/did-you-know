---
status: todo
service: shared
type: feature
ticket_id: TKT-002
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/shared_config_and_db_pool.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build shared/config_loader.py"
  - "Build shared/db.py with asyncpg pool"
  - "Create shared/__init__.py"
  - "Write tests for config_loader"
  - "Write tests for db pool"
history: []
comments: []
---

# [TKT-002] Shared Config Loader & DB Connection Pool

## Description
Build the shared infrastructure: YAML config loader with env var substitution, and async PostgreSQL connection pool using asyncpg.

## Dependencies
- **Blocks**: TKT-003, TKT-004, TKT-005, TKT-006, TKT-007, TKT-008, TKT-009, TKT-010
- **Blocked by**: TKT-001

## Technical Specification
See [docs/technical/shared_config_and_db_pool.md](docs/technical/shared_config_and_db_pool.md)

## Tasks
1. Build `shared/config_loader.py` — YAML loading, `${ENV_VAR}` substitution, caching
2. Build `shared/db.py` — asyncpg pool init/close, fetch/fetch_one/fetch_val/execute helpers, transaction context manager
3. Create `shared/__init__.py`
4. Write unit tests for config loader (env substitution, missing files, caching)
5. Write integration tests for DB pool (init, query, close lifecycle)

---
name: postgres_db
description: Native Postgres Database Management via Raw SQL Files
license: MIT
compatibility: opencode
---

# Skill: Postgres Database Management

## Context & Constraints
- **Migration Architecture**: Frameworkless raw SQL migration files located in `./migrations`.
- **Ordering Rule**: Migration files *must* follow a strict sequential naming convention (`0001_name.sql`, `0002_name.sql`).
- **Idempotency Execution**: Migrations are executed by a custom Python runner tracking state via the `schema_migrations` table.

## Tool Execution Protocols

### 1. Database Schema Alterations
- **Action**: When tasked with modifying schemas, adding tables, or creating indexes, the agent must *only* create a new sequential `.sql` file in the `./migrations` folder.
- **Transaction Rule**: Write SQL safely assuming that the whole file runs inside an implicit atomic transaction (`BEGIN` / `COMMIT` handled by the runner script).
- **Constraint**: Never inject structural queries directly into application logic files or run them manually in an open database session during tasks.

### 2. Indexing & Constraints Guardrails
- **Naming Standard**: Explicitly name all indexes (`idx_[table]_[columns]`) and constraints (`fk_[table]_[referenced_table]`).
- **Performance Checklist**: Include optimized indexes immediately on all foreign keys and frequently queried timestamp columns. Use `EXPLAIN (ANALYZE, BUFFERS)` to evaluate heavy data layouts.
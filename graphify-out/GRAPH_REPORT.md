# Graph Report - did-you-know  (2026-05-31)

## Corpus Check
- 59 files · ~31,935 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 760 nodes · 794 edges · 66 communities (63 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a30eb0af`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 65|Community 65]]

## God Nodes (most connected - your core abstractions)
1. `DatabaseTool` - 22 edges
2. `run_migrations()` - 19 edges
3. `Database Connection Tool for OpenCode Agents` - 13 edges
4. `AI Content Channel - Architecture` - 13 edges
5. `bash` - 11 edges
6. `Ticket Movement Commands` - 11 edges
7. `techlead` - 10 edges
8. `str` - 10 edges
9. `MigrationError` - 10 edges
10. `_parse_migration_files()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `TestMigrationParsing` --uses--> `MigrationError`  [INFERRED]
  tests/test_migrate.py → shared/migrate.py
- `TestMigrationRunner` --uses--> `MigrationError`  [INFERRED]
  tests/test_migrate.py → shared/migrate.py
- `TestConnectionRetry` --uses--> `MigrationError`  [INFERRED]
  tests/test_migrate.py → shared/migrate.py
- `example_basic_usage()` --calls--> `DatabaseTool`  [INFERRED]
  .opencode/tools/example_usage.py → .opencode/tools/database_tool.py
- `example_data_quality_check()` --calls--> `DatabaseTool`  [INFERRED]
  .opencode/tools/example_usage.py → .opencode/tools/database_tool.py

## Import Cycles
- None detected.

## Communities (66 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (33): Any, bool, float, int, str, DatabaseTool, main(), Determine database type from URL.                  Args:             url: Databa (+25 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (33): Approval Criteria, Backend Services (Python), Component Architecture, CRITICAL — Error Handling, CRITICAL — Security, CRITICAL — Security, Dashboard Service (React Frontend), Diagnostic Commands (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (29): 1. Current State Analysis, 1. Modularity & Separation of Concerns, 2. Requirements Gathering, 2. Scalability, 3. Design Proposal, 3. Maintainability, 4. Security, 4. Trade-Off Analysis (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (26): 1. Check Database Health, 2. Inspect Table Structure, 3. View Recent Data, 4. Check Data Quality, Basic Usage, Built-in Methods, Common Debugging Scenarios, Configuration (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (25): Add Comment to Ticket, Add PR Information, Bootstrap Board, Bug Fix with Review, Code Review Process, Common Workflows, Documentation Complete, Documentation-Only Ticket (+17 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (24): AI Content Channel - Architecture, APScheduler Configuration, Core Principles, Data Model, db.py, Entities, Environment Variables (.env), models.py (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (23): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+15 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (15): Integration tests for the actual schema migrations., Verify all tables, indexes, and constraints are created correctly., Verify all tables, indexes, and constraints are created correctly., Integration tests for the actual schema migrations., Verify CHECK constraints on status columns., Verify CHECK constraints on status columns., Create a test database connection., Verify updated_at triggers work correctly. (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (17): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+9 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (16): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+8 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (16): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (16): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (15): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.20
Nodes (17): Connection, _connect_with_retry(), _ensure_migrations_table(), _get_applied_versions(), _get_dsn_from_env(), main(), float, int (+9 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (15): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (15): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+7 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (15): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (15): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (17): id, id, id, id, deepseek-v3.2, deepseek-v4-flash, gemma-4-31b-it, grok-4.1 (+9 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (14): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (14): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+6 more)

### Community 21 - "Community 21"
Cohesion: 0.14
Nodes (13): 1. Before Implementation, 2. During Implementation, 3. Testing (MANDATORY), 4. Code Quality, Code Organization, Coding Principles, Developer Role - Code Implementation, General Principles (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.14
Nodes (13): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.15
Nodes (12): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (12): developer, maxTokens, min_p, mode, model, permissions, prompt, temperature (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.17
Nodes (11): 1. Feature Overview, 2. Service Ownership, 3. Detailed Implementation, 4. Error Handling, 5. Input/Output Specifications, 6. Edge Cases, 7. Dependencies, 8. Testing Requirements (+3 more)

### Community 26 - "Community 26"
Cohesion: 0.21
Nodes (8): _parse_migration_files(), Parse migration files from directory., Test migration file parsing and validation., Test parsing valid migration files., Test that invalid filenames are skipped with warning., Test detection of missing migration versions., Test that migrations are ordered by version., TestMigrationParsing

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (13): Agent Responsibilities, Configuration Guidelines for `.env.test`, Development Environment, Environment Configuration, Exceptions:, Expected File Structure, graphify, graphify (MANDATORY REPOSITORY NAVIGATION) (+5 more)

### Community 28 - "Community 28"
Cohesion: 0.20
Nodes (10): architect, extra_body, min_p, mode, model, prompt, temperature, top_p (+2 more)

### Community 29 - "Community 29"
Cohesion: 0.20
Nodes (9): Database Schema, Development, Did You Know? - AI Content Channel, License, Migration Runner, Project Structure, Quick Start, Setting up development environment (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.20
Nodes (8): Exception, MigrationError, Raised when a migration fails to apply., Tests for the migration runner., Test MigrationError exception formatting., Test connection retry logic., Test the retry logic (mocked)., TestConnectionRetry

### Community 31 - "Community 31"
Cohesion: 0.25
Nodes (5): Test successful migration application., Test error handling for bad migration SQL., Test the migration runner integration., Create a test migrations directory., TestMigrationRunner

### Community 32 - "Community 32"
Cohesion: 0.22
Nodes (8): 1. Check Project Documentation, 2. Run Tests (CONCISE OUTPUT), Output Format Guidelines, QA Role - Testing and Verification, Responsibilities, Rules, Test Creation Verification, Testing Process

### Community 33 - "Community 33"
Cohesion: 0.22
Nodes (8): 1. Code Quality & Linting, 2. Testing Framework, 3. Type Safety, 4. Logging & Tracing Frameworks, 5. Debugging & Issue Resolution Protocol, Context & Constraints, Skill: Python & API Development, Tool Execution Protocols

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (8): techlead, maxTokens, min_p, mode, model, prompt, temperature, top_p

### Community 35 - "Community 35"
Cohesion: 0.29
Nodes (8): permission, *, *.md, edit, write, permission, *, *.md

### Community 36 - "Community 36"
Cohesion: 0.29
Nodes (7): qa, min_p, mode, model, permission, prompt, temperature

### Community 37 - "Community 37"
Cohesion: 0.29
Nodes (7): reviewer, min_p, mode, model, permission, prompt, temperature

### Community 38 - "Community 38"
Cohesion: 0.29
Nodes (7): writer, min_p, mode, model, permission, prompt, temperature

### Community 39 - "Community 39"
Cohesion: 0.29
Nodes (7): *, cat board/*, git *, ls *, mkdir *, mv board/*, bash

### Community 40 - "Community 40"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-009] Module 4: Visual Generator

### Community 41 - "Community 41"
Cohesion: 0.33
Nodes (5): 1. Database Schema Alterations, 2. Indexing & Constraints Guardrails, Context & Constraints, Skill: Postgres Database Management, Tool Execution Protocols

### Community 42 - "Community 42"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-001] Database Schema & Migration Runner

### Community 43 - "Community 43"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-002] Shared Config Loader & DB Connection Pool

### Community 44 - "Community 44"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-003] Shared Pydantic Models

### Community 45 - "Community 45"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-004] OpenRouter API Client

### Community 46 - "Community 46"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-005] YAML Configuration Files

### Community 47 - "Community 47"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-006] Module 1: Trend Selector

### Community 48 - "Community 48"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-007] Module 2: Theme Associator

### Community 49 - "Community 49"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-008] Module 3: Content Generator

### Community 50 - "Community 50"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-010] Module 5: FastAPI Application & Web UI

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-011] Module 6: Platform Poster — DEFERRED

### Community 52 - "Community 52"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-012] APScheduler & CLI Entrypoint

### Community 54 - "Community 54"
Cohesion: 0.40
Nodes (4): agent, instructions, plugin, $schema

### Community 55 - "Community 55"
Cohesion: 0.50
Nodes (3): Architectural Structure & Lifespan, Context & Constraints, Skill: FastAPI REST Pattern

### Community 65 - "Community 65"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-001] Database Schema & Migration Runner

## Knowledge Gaps
- **469 isolated node(s):** `$schema`, `instructions`, `id`, `id`, `id` (+464 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `agent` connect `Community 54` to `Community 34`, `Community 36`, `Community 37`, `Community 38`, `Community 24`, `Community 28`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Why does `run_migrations()` connect `Community 13` to `Community 26`, `Community 7`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **Why does `provider` connect `Community 18` to `Community 54`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `DatabaseTool` (e.g. with `example_basic_usage()` and `example_data_quality_check()`) actually correct?**
  _`DatabaseTool` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `instructions`, `id` to the rest of the system?**
  _526 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06901960784313725 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.058823529411764705 - nodes in this community are weakly interconnected._
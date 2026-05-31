# Graph Report - did-you-know  (2026-05-31)

## Corpus Check
- 59 files · ~40,582 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1339 nodes · 1938 edges · 93 communities (89 shown, 4 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 288 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8931daef`
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
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]

## God Nodes (most connected - your core abstractions)
1. `AsyncMock` - 55 edges
2. `Trend` - 49 edges
3. `MagicMock` - 40 edges
4. `TrendSelector` - 36 edges
5. `ContentOption` - 31 edges
6. `Post` - 27 edges
7. `TestTrend` - 26 edges
8. `TestContentOption` - 26 edges
9. `TrendSelector` - 24 edges
10. `Theme` - 24 edges

## Surprising Connections (you probably didn't know these)
- `int` --uses--> `Trend`  [INFERRED]
  modules/trend_selector.py → shared/models.py
- `float` --uses--> `Trend`  [INFERRED]
  modules/trend_selector.py → shared/models.py
- `bool` --uses--> `Trend`  [INFERRED]
  modules/trend_selector.py → shared/models.py
- `AsyncMock` --uses--> `TrendSelector`  [INFERRED]
  tests/test_trend_selector.py → modules/trend_selector.py
- `MagicMock` --uses--> `TrendSelector`  [INFERRED]
  tests/test_trend_selector.py → modules/trend_selector.py

## Import Cycles
- None detected.

## Communities (93 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (35): Any, bool, Any, bool, float, int, str, DatabaseTool (+27 more)

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
Cohesion: 0.10
Nodes (17): Run all pending migrations.          Args:         dsn: PostgreSQL connection st, run_migrations(), Integration tests for the actual schema migrations., Verify all tables, indexes, and constraints are created correctly., Verify all tables, indexes, and constraints are created correctly., Integration tests for the actual schema migrations., Verify CHECK constraints on status columns., Verify CHECK constraints on status columns. (+9 more)

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
Cohesion: 0.19
Nodes (16): Connection, _connect_with_retry(), _ensure_migrations_table(), _get_applied_versions(), _get_dsn_from_env(), main(), Connection, float (+8 more)

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
Cohesion: 0.10
Nodes (20): id, id, options, id, id, deepseek-v3.2, deepseek-v4-flash, gemma-4-31b-it (+12 more)

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
Cohesion: 0.24
Nodes (7): Exception, MigrationError, Raised when a migration fails to apply., Tests for the migration runner., Test connection retry logic., Test the retry logic (mocked)., TestConnectionRetry

### Community 31 - "Community 31"
Cohesion: 0.20
Nodes (6): Test successful migration application., Test error handling for bad migration SQL., Test MigrationError exception formatting., Test the migration runner integration., Create a test migrations directory., TestMigrationRunner

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

### Community 66 - "Community 66"
Cohesion: 0.05
Nodes (23): Tests for shared/db.py., Test the query helper functions., Set up a mock pool for each test., Test fetch returns all rows., Test fetch_one returns a single row., Test fetch_one returns None when no rows., Test fetch_val returns a single value., Test execute returns status string. (+15 more)

### Community 67 - "Community 67"
Cohesion: 0.05
Nodes (21): Tests for shared/config_loader.py., Test loading a valid YAML config file., Test that env vars are substituted in loaded config., Test that config is cached after first load., Test that malformed YAML raises an error., Test that shortcut functions call load_config correctly., Test environment variable substitution logic., Test basic ${VAR_NAME} substitution. (+13 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (25): Pool, Record, close_pool(), execute(), execute_many(), fetch(), fetch_one(), fetch_val() (+17 more)

### Community 69 - "Community 69"
Cohesion: 0.20
Nodes (17): clear_cache(), get_backup_trends(), get_content_template(), get_platforms_config(), load_config(), Any, str, YAML config loader with ${ENV_VAR} substitution and caching. (+9 more)

### Community 70 - "Community 70"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-002] Shared Config Loader & DB Connection Pool

### Community 71 - "Community 71"
Cohesion: 0.19
Nodes (20): Enum, did-you-know shared utilities.  Provides: - config_loader: YAML config loading w, content_option_from_record(), ContentStatus, Platform, post_from_record(), PostStatus, Any (+12 more)

### Community 72 - "Community 72"
Cohesion: 0.33
Nodes (5): Dependencies, Description, Tasks, Technical Specification, [TKT-002] Shared Config Loader & DB Connection Pool

### Community 73 - "Community 73"
Cohesion: 0.09
Nodes (26): BaseModel, ApproveRequest, CancelRequest, PostResponse, No body needed — just the content_option_id from URL path., No body needed — just the content_option_id from URL path., No body needed — regenerates using existing theme., No body needed — regenerates using existing image_prompt. (+18 more)

### Community 74 - "Community 74"
Cohesion: 0.12
Nodes (14): ContentOption, Represents a generated content option (text + image prompt + optional image)., Test ContentOption model creation and validation., Valid ContentOption with all required fields., Valid ContentOption with all optional fields populated., Platform can be created from string enum value., Invalid platform string should raise ValidationError., Empty fact (min_length=1) should raise ValidationError. (+6 more)

### Community 75 - "Community 75"
Cohesion: 0.08
Nodes (13): TrendSelector module — selects trending topics from Google Trends.  Provides the, Represents a trending keyword from Google Trends., Trend, Score < 0 should raise ValidationError., Score > 100 should raise ValidationError., Boundary values for score (0.0 and 100.0)., Missing keyword should raise ValidationError., Empty keyword (min_length=1) should raise ValidationError. (+5 more)

### Community 76 - "Community 76"
Cohesion: 0.14
Nodes (12): Post, Represents a published post on a platform.     Platform is inherited from the pa, Test Post model creation and validation., Valid Post with all required fields., Valid Post with all optional fields populated., Post with FAILED status and error message., Missing content_option_id should raise ValidationError., Missing platform should raise ValidationError. (+4 more)

### Community 77 - "Community 77"
Cohesion: 0.17
Nodes (10): Represents a short theme name derived from a trend., Theme, Test Theme model creation and validation., Valid Theme with all required fields., Valid Theme with optional fields populated., Empty name (min_length=1) should raise ValidationError., Name exceeding max_length should raise ValidationError., Missing trend_id should raise ValidationError. (+2 more)

### Community 78 - "Community 78"
Cohesion: 0.17
Nodes (7): Test model_dump() and model_dump_json() round-trip., ContentOption serializes and deserializes correctly., ContentOption serializes to JSON and back., HealthResponse serializes and deserializes correctly., Post serializes to JSON and back., Enum fields should serialize to their string values., TestSerialization

### Community 79 - "Community 79"
Cohesion: 0.32
Nodes (6): ContentOptionResponse, API response for a single content option., Test ContentOptionResponse API model., Valid ContentOptionResponse with all fields., image_url should default to None., TestContentOptionResponse

### Community 80 - "Community 80"
Cohesion: 0.32
Nodes (6): HealthResponse, Health check response., Test HealthResponse API model., Valid HealthResponse., Default status and database values., TestHealthResponse

### Community 81 - "Community 81"
Cohesion: 0.06
Nodes (29): AsyncMock, MagicMock, Test that init_pool accepts an explicit DSN., Test generate_text with response_format for JSON mode., Test that empty prompt raises ValueError., Test that whitespace-only prompt raises ValueError., Test that empty choices array raises OpenRouterError., Test that 401 errors raise immediately without retry. (+21 more)

### Community 82 - "Community 82"
Cohesion: 0.06
Nodes (43): AsyncClient, bytes, Response, OpenRouterClient, OpenRouterError, OpenRouterRateLimitError, _parse_retry_after(), float (+35 more)

### Community 83 - "Community 83"
Cohesion: 0.08
Nodes (18): Core selection algorithm., Backup fallback behaviour., First backup trend is used when none have been used recently., Backup trends that have been used recently are skipped., When every backup trend has been used, returns None., No backup trends configured -> None., Saved backup trend has source='backup'., Additional edge-case coverage. (+10 more)

### Community 84 - "Community 84"
Cohesion: 0.16
Nodes (15): Any, float, int, str, Fetch trending searches from Google Trends API.          Fallback chain:, Parse the DataFrame returned by ``trending_searches()``.          Assigns a scor, Parse the data returned by ``realtime_trending_searches()``.          Extracts k, Query the ``trends`` table for keywords used in the last *days* days.          R (+7 more)

### Community 85 - "Community 85"
Cohesion: 0.13
Nodes (12): _is_food_related(), bool, Check whether a keyword appears to be food-related.      Performs a case-insensi, db_pool(), Tests for modules/trend_selector.py — TrendSelector class.  Covers: - ``_select_, Full config dict as loaded from backup_trends.yaml., Mock asyncpg connection pool with async helpers., TrendSelector instance with mocked db pool and sample config. (+4 more)

### Community 86 - "Community 86"
Cohesion: 0.12
Nodes (9): Test *_from_record() helper functions., Convert a dict-like record to ContentOption., Record with no hashtags should default to empty list., Convert a dict-like record to Trend., Record without source should get default., Convert a dict-like record to Theme., Convert a dict-like record to Post., Record with FAILED status and error message. (+1 more)

### Community 87 - "Community 87"
Cohesion: 0.14
Nodes (8): pytrends integration (mocked)., Successfully fetches and parses trending searches., Returns empty list when trending_searches() raises., Falls through to realtime_trending_searches when trending_searches fails., When pytrends is not installed, returns empty list., Handles realtime returning an empty dict gracefully., Handles empty DataFrame from trending_searches()., TestFetchTrends

### Community 88 - "Community 88"
Cohesion: 0.14
Nodes (8): Full pipeline integration tests (mocked)., Full flow: fetch -> dedup -> save -> return Trend., When all API trends have been used, falls back to backup trends., When the API fails, uses backup trends., When API fails and all backups are used, returns None., When pytrends is not installed, uses backup trends., When API returns empty list, uses backup trends., TestRun

### Community 89 - "Community 89"
Cohesion: 0.20
Nodes (6): Unit tests for the parsing methods., Scores decrease by 5 from 100 for each trend., Extracts keywords from realtime trending entries., Empty entries list returns empty list., Empty dict returns empty list., TestParseTrendingSearches

### Community 90 - "Community 90"
Cohesion: 0.25
Nodes (5): Database INSERT operations., Inserts a trend and returns a Trend model with generated id., Raises RuntimeError if INSERT RETURNING yields no row., Verifies the SQL query and parameters passed to the DB., TestSaveTrend

### Community 91 - "Community 91"
Cohesion: 0.50
Nodes (3): Config.from_attributes should be True for ORM compatibility., Test Trend model creation and validation., TestTrend

## Knowledge Gaps
- **485 isolated node(s):** `$schema`, `instructions`, `id`, `id`, `id` (+480 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Trend` connect `Community 75` to `Community 71`, `Community 73`, `Community 74`, `Community 76`, `Community 77`, `Community 78`, `Community 79`, `Community 80`, `Community 81`, `Community 83`, `Community 84`, `Community 85`, `Community 86`, `Community 87`, `Community 88`, `Community 89`, `Community 90`, `Community 91`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `AsyncMock` connect `Community 81` to `Community 66`, `Community 75`, `Community 82`, `Community 83`, `Community 84`, `Community 85`, `Community 87`, `Community 88`, `Community 90`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `MagicMock` connect `Community 81` to `Community 66`, `Community 75`, `Community 82`, `Community 83`, `Community 84`, `Community 87`, `Community 88`, `Community 89`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `AsyncMock` (e.g. with `TrendSelector` and `Trend`) actually correct?**
  _`AsyncMock` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `Trend` (e.g. with `AsyncMock` and `MagicMock`) actually correct?**
  _`Trend` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `MagicMock` (e.g. with `TrendSelector` and `Trend`) actually correct?**
  _`MagicMock` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `TrendSelector` (e.g. with `TrendSelector` and `Trend`) actually correct?**
  _`TrendSelector` has 2 INFERRED edges - model-reasoned connections that need verification._
---
status: todo
service: app
type: feature
ticket_id: TKT-012
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/scheduler_and_cli.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build app/scheduler.py with APScheduler jobs"
  - "Integrate scheduler in FastAPI lifespan"
  - "Build main.py CLI entrypoint"
  - "Create pyproject.toml project scripts"
  - "Write pipeline orchestration tests"
history: []
comments: []
---

# [TKT-012] APScheduler & CLI Entrypoint

## Description
Integrate APScheduler for automated 2-hour pipeline execution and build CLI entrypoint with `serve`, `generate`, and `migrate` commands. This is the final integration ticket that ties all modules together.

## Dependencies
- **Blocks**: None (final ticket)
- **Blocked by**: TKT-001, TKT-002, TKT-004, TKT-005, TKT-006, TKT-007, TKT-008, TKT-009, TKT-010

## Technical Specification
See [docs/technical/scheduler_and_cli.md](docs/technical/scheduler_and_cli.md)

## Tasks
1. Build `app/scheduler.py` — `setup_scheduler()` and `run_pipeline()` orchestrating all modules
2. Update `app/main.py` lifespan — init DB pool, OpenRouter client, configs, start scheduler
3. Build `main.py` CLI — `click` group with `migrate`, `serve`, `generate` commands
4. Update `pyproject.toml` — add `[project.scripts]` entry for CLI
5. Write tests: mock modules, test pipeline orchestration, test CLI commands

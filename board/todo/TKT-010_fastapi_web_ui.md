---
status: todo
service: app
type: feature
ticket_id: TKT-010
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/module_fastapi_web_ui.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build FastAPI app with lifespan"
  - "Build all API endpoints in routes.py"
  - "Create dashboard.html template"
  - "Create preview templates (base, pinterest, instagram)"
  - "Mount static files for image serving"
  - "Write endpoint tests"
history: []
comments: []
---

# [TKT-010] Module 5: FastAPI Application & Web UI

## Description
Build the FastAPI web application with REST API endpoints for content management and Jinja2 HTML dashboard for reviewing, approving, and managing content options. Dashboard includes platform tabs for filtering (All | Pinterest | Instagram). Includes platform preview templates.

## Dependencies
- **Blocks**: TKT-012
- **Blocked by**: TKT-001, TKT-002, TKT-003, TKT-008, TKT-009

## Technical Specification
See [docs/technical/module_fastapi_web_ui.md](docs/technical/module_fastapi_web_ui.md)

## Tasks
1. Build `app/main.py` — FastAPI app with lifespan (DB pool init/close), static file mount
2. Build `app/routes.py` — all endpoints (dashboard with platform filter, detail, approve, cancel, regenerate-text, regenerate-image, preview, history, health)
3. Create `app/templates/dashboard.html` — grid of pending option cards with platform badges, platform filter tabs, action buttons
4. Create `app/templates/preview/base.html` — shared preview layout
5. Create `app/templates/preview/pinterest.html` — pin-style preview with char/hashtag counts
6. Create `app/templates/preview/instagram.html` — post-style preview with char/hashtag counts
7. Write endpoint tests with mocked DB

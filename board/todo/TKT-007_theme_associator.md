---
status: todo
service: modules
type: feature
ticket_id: TKT-007
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/module_theme_associator.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build ThemeAssociator class"
  - "Implement OpenRouter theme generation"
  - "Implement theme deduplication"
  - "Write tests with mocked OpenRouter"
history: []
comments: []
---

# [TKT-007] Module 2: Theme Associator

## Description
Build the Theme Associator module that creates short, memorable theme names (max 3 words) from trend keywords using OpenRouter AI. Includes deduplication to avoid recently used themes.

## Dependencies
- **Blocks**: TKT-008
- **Blocked by**: TKT-001, TKT-002, TKT-003, TKT-004, TKT-005, TKT-006

## Technical Specification
See [docs/technical/module_theme_associator.md](docs/technical/module_theme_associator.md)

## Tasks
1. Build `ThemeAssociator` class with `run(trend)` method
2. Implement `_generate_theme()` — OpenRouter call with theme_prompt template
3. Implement `_is_duplicate()` — ILIKE-based fuzzy matching against recent themes
4. Implement retry flow: if duplicate, request alternative (max 2 retries)
5. Write unit tests: mock OpenRouter, test prompt formatting, test dedup matching

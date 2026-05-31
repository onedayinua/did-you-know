---
status: todo
service: modules
type: feature
ticket_id: TKT-006
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/module_trend_selector.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build TrendSelector class"
  - "Implement pytrends integration"
  - "Implement trend deduplication logic"
  - "Implement backup trend fallback"
  - "Write tests with mocked pytrends"
history: []
comments: []
---

# [TKT-006] Module 1: Trend Selector

## Description
Build the Trend Selector module that fetches trending culinary topics from Google Trends via `pytrends`, deduplicates against recently used trends in the database, and saves the best unused trend.

## Dependencies
- **Blocks**: TKT-007
- **Blocked by**: TKT-001, TKT-002, TKT-003, TKT-005

## Technical Specification
See [docs/technical/module_trend_selector.md](docs/technical/module_trend_selector.md)

## Tasks
1. Build `TrendSelector` class with `run()` method
2. Implement `_fetch_trends()` — pytrends integration with food category filter
3. Implement `_get_used_keywords()` + `_select_best()` — deduplication logic
4. Implement `_use_backup()` — fallback to `backup_trends.yaml` on API failure
5. Write unit tests: mock pytrends responses, test selection algorithm, test fallback chain

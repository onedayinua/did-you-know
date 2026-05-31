---
status: todo
service: modules
type: feature
ticket_id: TKT-011
deferred: true
deferred_reason: "Posting will be done manually initially. Will implement when automated posting is needed."
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/module_platform_poster.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build PlatformPoster class"
  - "Implement platform dispatch (handler map)"
  - "Implement content formatting for posting"
  - "Implement Pinterest API posting"
  - "Stub Instagram posting"
  - "Implement DB status updates"
  - "Write tests with mocked platform APIs"
history: []
comments: []
---

# [TKT-011] Module 6: Platform Poster — DEFERRED

> **Status: Deferred.** Posting will be done manually initially. This ticket will be implemented when automated posting is needed.

## Description
Build the Platform Poster module that posts approved content to its target platform. Platform is already specified on the content option (from Module 3), so no platform iteration needed. Content is already sized correctly per platform. Pinterest is fully implemented; Instagram is stubbed.

## Dependencies
- **Blocks**: None (decoupled from pipeline — posting is manual initially)
- **Blocked by**: TKT-001, TKT-002, TKT-003, TKT-005

## Technical Specification
See [docs/technical/module_platform_poster.md](docs/technical/module_platform_poster.md)

## Tasks
1. Build `PlatformPoster` class with `run(content_option_id)` method returning single `Post`
2. Implement `_format_for_posting()` — assemble caption from pre-sized fact + hashtags
3. Implement platform dispatch (platform → handler mapping)
4. Implement `_post_to_pinterest()` — Pinterest API v5 pin creation
5. Stub `_post_to_instagram()` — placeholder for future implementation
6. Implement `_create_post_record()` + `_update_post_result()` — DB operations
7. Write unit tests: mock httpx, test formatting, test dispatch, test error handling

---
status: todo
service: modules
type: feature
ticket_id: TKT-008
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/module_content_generator.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build ContentGenerator class"
  - "Implement queue size check and expiry"
  - "Implement text variation generation"
  - "Implement image prompt generation"
  - "Implement batch save to DB"
  - "Write tests"
history: []
comments: []
---

# [TKT-008] Module 3: Content Generator

## Description
Build the Content Generator module that creates N platform-specific content options (fact + hashtags + image prompt) from a theme. Iterates over enabled platforms, generates text tailored to each platform's constraints (character limit, hashtag count), then generates image prompts. Includes queue management (max_pending check, old option expiry).

## Dependencies
- **Blocks**: TKT-009, TKT-010
- **Blocked by**: TKT-001, TKT-002, TKT-003, TKT-004, TKT-005, TKT-007

## Technical Specification
See [docs/technical/module_content_generator.md](docs/technical/module_content_generator.md)

## Tasks
1. Build `ContentGenerator` class with `run(theme, platforms)` method
2. Implement `_check_queue()` and `_expire_old_options()` — queue management
3. Implement `_generate_text_variations()` — OpenRouter call with text_prompt + platform constraints, JSON mode
4. Implement `_generate_image_prompt()` — OpenRouter call with image_prompt template
5. Implement `_save_options()` — batch INSERT into content_options with platform field
6. Write unit tests: mock OpenRouter, test queue logic, test JSON parsing, test per-platform generation

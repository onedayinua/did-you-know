---
status: todo
service: modules
type: feature
ticket_id: TKT-009
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/module_visual_generator.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build VisualGenerator class"
  - "Implement image generation via OpenRouter"
  - "Implement image file saving to data/images/"
  - "Implement DB update for image_path"
  - "Write tests"
history: []
comments: []
---

# [TKT-009] Module 4: Visual Generator

## Description
Build the Visual Generator module that creates images for content options using OpenRouter image generation (DALL-E). Images are saved to `data/images/` and paths recorded in the database.

## Dependencies
- **Blocks**: TKT-010
- **Blocked by**: TKT-001, TKT-002, TKT-003, TKT-004, TKT-005, TKT-008

## Technical Specification
See [docs/technical/module_visual_generator.md](docs/technical/module_visual_generator.md)

## Tasks
1. Build `VisualGenerator` class with `run(content_option_ids)` method
2. Implement `_get_pending_options()` — query for options with image_prompt but no image_path
3. Implement `_generate_and_save()` — OpenRouter image generation + file write
4. Implement `_update_image_path()` — UPDATE content_options with saved path
5. Write tests: mock OpenRouter, test file naming, test dimension mapping

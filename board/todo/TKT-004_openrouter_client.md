---
status: todo
service: shared
type: feature
ticket_id: TKT-004
created: "2026-05-31T00:00:00Z"
tech_spec: docs/technical/shared_openrouter_client.md
pr:
  url: ""
  branch: ""
tasks:
  - "Build OpenRouterClient class with httpx"
  - "Implement generate_text() method"
  - "Implement generate_image() method"
  - "Add retry logic with exponential backoff"
  - "Define error classes (OpenRouterError, OpenRouterRateLimitError)"
  - "Write tests with mocked HTTP responses"
history: []
comments: []
---

# [TKT-004] OpenRouter API Client

## Description
Build an async HTTP client wrapper for OpenRouter API supporting text generation (chat completions) and image generation. Includes retry logic with exponential backoff for transient failures.

## Dependencies
- **Blocks**: TKT-007, TKT-008, TKT-009
- **Blocked by**: TKT-002

## Technical Specification
See [docs/technical/shared_openrouter_client.md](docs/technical/shared_openrouter_client.md)

## Tasks
1. Build `OpenRouterClient` class with lazy httpx client initialization
2. Implement `generate_text()` — chat completion API, JSON mode support
3. Implement `generate_image()` — image generation API, returns bytes
4. Add retry logic: exponential backoff on 429/5xx, max 3 retries
5. Define `OpenRouterError` and `OpenRouterRateLimitError` exception classes
6. Write unit tests: mock httpx, test retry timing, test error handling

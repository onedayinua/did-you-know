---
name: kanban
description: Backend Python & API Development
license: MIT
compatibility: opencode
---

# Skill: Python & API Development

## Context & Constraints
- **Scope**: Applied to all Python backend and API development tasks.
- **Language Level**: Python 3.10+ with strict type hinting on all new or modified function signatures.

## Tool Execution Protocols

### 1. Code Quality & Linting
- **Tool**: `ruff`
- **Behavior**: Run `ruff check --fix` and `ruff format` before completing any coding task. 

### 2. Testing Framework
- **Tool**: `pytest`
- **Execution Command**: `pytest --lf --tb=short`

### 3. Type Safety
- **Requirement**: Enforce PEP 484 type hints on all functions.

### 4. Logging & Tracing Frameworks
- **Primary Library**: Standard library `logging` configured with standard structured handlers, or `structlog`.
- **Tracing Library**: `opentelemetry` (OpenTelemetry SDK).
- **Core Requirement**: Ensure the logging formatter is configured to automatically inject `trace_id` and `span_id` into the JSON log payload.

### 5. Debugging & Issue Resolution Protocol
- **Trace Investigation**: When debugging a failure, the agent must first locate the failing `trace_id` and filter all system logs by that ID to reconstruct the exact execution path.
- **Active Code Instrumentation**: If the root cause is unclear, the agent must strategically inject *new* temporary `logger.debug()` or `logger.info()` statements into the codebase. 
- **Instrumentation Rule**: These temporary logs must utilize the active tracer context so they are bound to the same `trace_id` as the failing request.
- **Error Capture**: Every `logger.exception()` block *must* include `exc_info=True` to capture the full traceback.
- **Constraint**: Never use standard `print()` statements for debugging or application logging.
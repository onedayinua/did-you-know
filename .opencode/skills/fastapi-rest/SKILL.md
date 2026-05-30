---
name: fast_api
description: FastAPI REST API Pattern & Architecture
license: MIT
compatibility: opencode
---

# Skill: FastAPI REST Pattern

## Context & Constraints
- **Scope**: Applied to all HTTP/REST microservices and API layers.
- **Prefix Rule**: All routes *must* be structured under an explicit `/api` prefix via `APIRouter`.
- **Async Execution**: Every route handler and dependency must use native `async def` syntax.

## Architectural Structure & Lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup resources (DB pools, clients, tracer engines)
    yield
    # Graceful teardown of all allocated resources

app = FastAPI(title="Service API", lifespan=lifespan)
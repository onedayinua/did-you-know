# FastAPI REST Pattern

## Purpose
Standard REST API structure for services that expose HTTP endpoints.

## Basic Structure
```python
from fastapi import FastAPI, HTTPException, Query
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB, Redis, etc.
    app.state.db = await connect_db()
    yield
    # Shutdown: close connections
    await app.state.db.close()

app = FastAPI(title="Data Service API", lifespan=lifespan)
```

## Endpoint Structure
- All endpoints under `/api/` prefix
- Health endpoint always at `/api/health`
- Use async handlers
- Return proper HTTP status codes

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api")

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "data-service",
        "db_connected": True,
        "redis_connected": True
    }

@router.get("/ohlcv")
async def get_ohlcv(
    asset_id: int = Query(..., gt=0),
    start: str = Query(..., description="ISO date string"),
    end: str = Query(..., description="ISO date string")
):
    # Validate inputs
    # Query database
    # Return data
    return {"data": [...], "count": 0}

@router.get("/ohlcv/latest")
async def get_latest_ohlcv(
    asset_id: int = Query(..., gt=0),
    limit: int = Query(10, gt=0, le=1000)
):
    return {"data": [...]}

@router.get("/assets")
async def list_assets():
    return {"assets": [...]}

@router.get("/assets/{asset_id}")
async def get_asset(asset_id: int):
    asset = await fetch_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset
```

## Error Handling
```python
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)}
    )

@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
```

## Running the Server
```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
```

## Required Endpoints (all services with REST)
- `GET /api/health` - service health status
- Service-specific data endpoints per requirements

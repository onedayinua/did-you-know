# Module 5: FastAPI Application & Web UI

## 1. Feature Overview
**Purpose**: Provide a web dashboard for reviewing, approving, and managing content options with platform previews
**Business Value**: Human-in-the-loop approval ensures quality before posting
**Scope**: FastAPI app with REST API endpoints + Jinja2 HTML dashboard + platform preview templates
**Success Criteria**: Dashboard loads, shows pending options with images, approve/cancel/regenerate actions work, previews render correctly

## 2. Service Ownership
**Primary Service**: `app/main.py`, `app/routes.py`, `app/templates/`
**Dependent Services**: Module 3 (content_generator for regeneration), Module 4 (visual_generator for image regeneration)
**Interface Changes**: HTTP endpoints served on port 8000

## 3. Detailed Implementation

### File Structure

```
app/
├── main.py                  # FastAPI app + lifespan (mounts APScheduler)
├── routes.py                # All API endpoints
├── scheduler.py             # APScheduler job definitions (empty initially, filled in TKT-012)
└── templates/
    ├── dashboard.html       # Main dashboard page
    └── preview/
        ├── base.html        # Shared preview layout
        ├── pinterest.html   # Pinterest pin preview
        └── instagram.html   # Instagram post preview
```

### FastAPI App (`app/main.py`)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routes import router
from shared.db import init_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup: init DB pool
    await init_pool()
    yield
    # Shutdown: close DB pool
    await close_pool()

app = FastAPI(
    title="Did You Know - Content Channel",
    description="AI-driven culinary content management dashboard",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(router)

# Serve static files (images)
from fastapi.staticfiles import StaticFiles
app.mount("/images", StaticFiles(directory="data/images"), name="images")
```

### API Endpoints (`app/routes.py`)

```python
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
```

#### Endpoint Definitions

**1. Dashboard** — `GET /`
```python
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, platform: str | None = None):
    """Show all pending content options with images, optionally filtered by platform."""
    # Query: SELECT * FROM content_options WHERE status = 'pending'
    #        [AND platform = $1] if platform filter provided
    #        ORDER BY created_at DESC
    # Render: dashboard.html with options list + current platform filter
```

**2. Option Detail** — `GET /options/{id}`
```python
@router.get("/options/{id}", response_class=HTMLResponse)
async def option_detail(request: Request, id: int):
    """Show full details of a single content option."""
    # Query: SELECT * FROM content_options WHERE id = $1
    # Render: option detail page
    # Raises 404 if not found
```

**3. Approve Option** — `POST /options/{id}/approve`
```python
@router.post("/options/{id}/approve")
async def approve_option(id: int):
    """Approve option — marks content as ready for manual posting."""
    # 1. Update: UPDATE content_options SET status = 'approved' WHERE id = $1 AND status = 'pending'
    # 2. Return redirect to dashboard or JSON response
    # NOTE: Posting is manual initially (TKT-011 deferred). User posts to platform manually, then marks as posted.
```

**4. Cancel Option** — `POST /options/{id}/cancel`
```python
@router.post("/options/{id}/cancel")
async def cancel_option(id: int):
    """Cancel a content option."""
    # Update: UPDATE content_options SET status = 'cancelled' WHERE id = $1 AND status = 'pending'
    # Returns: redirect to dashboard
```

**5. Regenerate Text** — `POST /options/{id}/regenerate-text`
```python
@router.post("/options/{id}/regenerate-text")
async def regenerate_text(id: int):
    """Regenerate fact + hashtags, keep image."""
    # 1. Load option from DB
    # 2. Call content_generator._generate_text_variations(theme, count=1)
    # 3. Update: UPDATE content_options SET fact = $1, hashtags = $2, updated_at = NOW() WHERE id = $3
    # 4. Return updated option
```

**6. Regenerate Image** — `POST /options/{id}/regenerate-image`
```python
@router.post("/options/{id}/regenerate-image")
async def regenerate_image(id: int):
    """Regenerate image only, keep text."""
    # 1. Load option from DB
    # 2. Call visual_generator._generate_and_save(option, dimensions)
    # 3. Update image_path in DB
    # 4. Return updated option
```

**7. Preview** — `GET /preview/{id}`
```python
@router.get("/preview/{id}", response_class=HTMLResponse)
async def preview_all(request: Request, id: int):
    """Show preview of post across all platforms."""
    # Load option from DB
    # Render preview templates for each enabled platform
```

**8. Platform Preview** — `GET /preview/{id}/{platform}`
```python
@router.get("/preview/{id}/{platform}", response_class=HTMLResponse)
async def preview_platform(request: Request, id: int, platform: str):
    """Show preview for specific platform."""
    # Load option from DB
    # Render platform-specific template
    # Calculate character count vs limit, hashtag count vs limit
```

**9. History** — `GET /history`
```python
@router.get("/history", response_class=HTMLResponse)
async def history(request: Request, platform: str | None = None):
    """List posted content history, optionally filtered by platform."""
    # Query: SELECT co.*, p.post_url, p.status as post_status
    #        FROM content_options co
    #        JOIN posts p ON p.content_option_id = co.id
    #        WHERE co.status IN ('posted', 'expired', 'cancelled')
    #        [AND co.platform = $1] if platform filter provided
    #        ORDER BY co.created_at DESC
    # Render: history page
```

**10. Health Check** — `GET /health`
```python
@router.get("/health")
async def health():
    """Health check endpoint."""
    # Test DB connection: SELECT 1
    # Return: {"status": "ok", "database": true, "timestamp": "..."}
```

### Dashboard Template (`app/templates/dashboard.html`)

**Layout**:
- HTML5 page with inline CSS (no build step for MVP)
- Tab navigation for platform filtering: **All | Pinterest | Instagram**
- Grid layout showing pending option cards
- Each card displays:
  - **Platform badge** (colored: Pinterest=red, Instagram=purple)
  - Theme (bold heading)
  - Fact preview (truncated to 100 chars)
  - Hashtags (comma-separated)
  - Image thumbnail (from `/images/{filename}`)
  - Created date (relative: "2 hours ago")
  - Action buttons: View, Approve, Cancel

**Styling**:
- Clean, minimal design
- Card-based layout (CSS Grid, responsive)
- Image thumbnails: 200px max width
- Platform badges: small colored labels
- Color coding: pending=blue, approved=green, expired=gray

### Preview Templates (`app/templates/preview/`)

**base.html**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Preview{% endblock %}</title>
    <style>
        /* Shared preview styles */
        .preview-container { max-width: 600px; margin: 0 auto; }
        .preview-image { max-width: 100%; }
        .char-count { color: {% if over_limit %}red{% else %}green{% endif %}; }
    </style>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

**pinterest.html**:
- Pinterest pin layout: tall image (1000×1500) + title + description
- Shows character count vs 500 limit
- Shows hashtag count vs 5-10 range

**instagram.html**:
- Instagram post layout: square image (1080×1080) + caption
- Shows character count vs 2200 limit
- Shows hashtag count vs 10-30 range

## 4. Error Handling
**Expected Failures**:
- Option not found (404)
- Option not in correct status for action (409)
- Database query failure (500)
- Module call failure during regeneration (500)
- Image file not found (404)

**Recovery Strategies**:
- Not found: Return 404 with clear message
- Wrong status: Return 409 Conflict with current status
- DB failure: Return 500 with generic message, log details
- Module failure: Return 500 with error description
- Missing image: Show placeholder image

**Error Response Format**:
```json
{
    "detail": "Content option not found"
}
```

**Logging Requirements**:
- INFO: Request received, action completed
- WARNING: Option not found, wrong status
- ERROR: DB failure, module failure

## 5. Input/Output Specifications
**Input Validation**:
- `id`: positive integer (path parameter)
- `platform`: string, must be in configured platforms list

**Output Formats**:
- HTML pages: Full HTML5 documents
- API responses: JSON (for non-HTML endpoints)
- Redirects: 302 to dashboard after actions

## 6. Edge Cases
- Empty dashboard (no pending options)
- Very long fact text (truncate in UI)
- Image loading slow (lazy loading in HTML)
- Concurrent approvals of same option (status check prevents double-approve)
- Browser back button after approve (re-approve should be no-op)

## 7. Dependencies
- `fastapi` web framework
- `uvicorn` ASGI server
- `jinja2` templating
- `shared/db.py` (database access)
- `modules/content_generator.py` (for text regeneration)
- `modules/visual_generator.py` (for image regeneration)

## 8. Testing Requirements
- **Unit tests**: Test each endpoint with mocked DB
- **Integration tests**: Full HTTP request/response cycle with test DB
- **Template tests**: Verify HTML rendering with sample data
- **UI tests**: Manual verification of dashboard layout

## 9. Deployment Considerations
- **Migration**: Ensure `app/templates/` directory exists
- **Rollback**: N/A
- **Monitoring**: Log request count, response times
- **Performance**: Dashboard query should be indexed (status + created_at)
- **Security**: No authentication for MVP (local use only)

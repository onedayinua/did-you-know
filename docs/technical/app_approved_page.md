# app_approved_page.md

## 1. Feature Overview
**Purpose**: Add a dedicated "Approved" page that displays all content options with `status = 'approved'`, allowing users to view full previews and cancel approved items.

**Business Value**: Currently, approved items vanish from the dashboard with no dedicated management interface. This page gives users visibility into what they've approved and the ability to reverse approvals (via cancel) before posting is implemented.

**Scope**:
- New route `GET /approved` — list all approved content options, filterable by platform
- New route `POST /options/{id}/cancel` — already exists and works; the cancel endpoint currently only allows cancelling `pending` items. We need to extend it to also allow cancelling `approved` items.
- Full preview access via existing `/preview/{id}` route
- Navigation link in the header

**Out of Scope**:
- The "Post" button/feature (will be implemented later as stated)
- Any posting logic or integration with external platforms

**Success Criteria**:
- `GET /approved` returns HTML page showing all approved content options
- Each card shows image, platform badge, theme, fact, hashtags, meta info
- Each card has "Preview" link (opens in new tab) and "Cancel" button
- Cancel button on approved page works identically to dashboard cancel (sets status to `cancelled`, redirects back to `/approved`)
- Platform filter tabs work on the approved page
- Navigation header includes "Approved" link

## 2. Service Ownership
**Primary Service**: `app` (FastAPI routes + templates)

**Dependent Services**: None

**Interface Changes**:
- New route: `GET /approved` (HTML response)
- Modified route: `POST /options/{id}/cancel` — extend to allow cancelling `approved` items in addition to `pending` items

## 3. Detailed Implementation

### 3.1 New Route: `GET /approved`

**File**: `app/routes.py`

Add a new route handler `approved_page` at `GET /approved`:

```python
@router.get("/approved", response_class=HTMLResponse)
async def approved_page(request: Request, platform: str | None = None):
    """Show all approved content options, optionally filtered by platform."""
    if platform:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'approved'
            AND platform = $1
            ORDER BY created_at DESC
        """
        rows = await fetch(query, platform)
    else:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'approved'
            ORDER BY created_at DESC
        """
        rows = await fetch(query)

    options = [_row_to_dict(r) for r in rows]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "options": options,
            "current_platform": platform,
            "approved_mode": True,
        },
    )
```

### 3.2 Modify Cancel Endpoint

**File**: `app/routes.py`

Change the cancel endpoint's SQL to allow cancelling both `pending` and `approved` items:

```python
@router.post("/options/{id}/cancel")
async def cancel_option(id: int):
    result = await execute(
        "UPDATE content_options SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP "
        "WHERE id = $1 AND status IN ('pending', 'approved')",
        id,
    )
    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=409,
            detail="Option not found or not in pending/approved status",
        )
    logger.info("Cancelled content option id=%d", id)
    # Redirect back to the referring page (or dashboard as fallback)
    return RedirectResponse(url="/", status_code=302)
```

**Important**: The redirect URL should ideally go back to the page the user was on. Since the cancel endpoint is called from both the dashboard and the approved page, we need a way to redirect appropriately. Options:
1. Use a `Referer` header check (simple, but can be spoofed/missing)
2. Add a `next` query parameter to the form action

**Recommendation**: Use a `next` query parameter approach. The cancel form on the approved page will POST to `/options/{id}/cancel?next=/approved`, and the cancel form on the dashboard will POST to `/options/{id}/cancel?next=/`. The route handler reads `next` and redirects there.

### 3.3 Template Changes

**File**: `app/templates/dashboard.html`

The template already handles multiple modes via context variables (`history_mode`, `detail_mode`). We add `approved_mode` support:

1. **Header title**: When `approved_mode` is True, show "Approved Content" instead of "Pending Content"
2. **Tabs**: The platform filter tabs should link to `/approved?platform=...` when in approved mode
3. **Card rendering**: Reuse the existing card layout. Each card shows:
   - Image (or "No Image" placeholder)
   - Platform badge
   - Status badge (approved = green)
   - Theme, fact (truncated), hashtags, meta
   - Actions: "Preview" link + "Cancel" button
4. **Cancel form**: POST to `/options/{id}/cancel?next=/approved`
5. **Empty state**: When no approved items exist, show "No approved content" message

### 3.4 Navigation Update

Add "Approved" link to the header nav, between "Dashboard" and "History":
```html
<a href="/approved">Approved</a>
```

## 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| Cancel approved item | Works — sets status to `cancelled`, redirects to `/approved` |
| Cancel already-cancelled item | HTTP 409 — "Option not found or not in pending/approved status" |
| Cancel already-posted item | HTTP 409 — same as above |
| Cancel non-existent item | HTTP 409 — same as above |
| `next` parameter missing/invalid | Fallback to redirect to `/` |
| Database error during query | FastAPI returns HTTP 500 |

## 5. Input/Output Specifications

### `GET /approved`
- **Query params**: `platform` (optional, string: `"pinterest"` or `"instagram"`)
- **Response**: HTML page (same template as dashboard, with `approved_mode=True`)

### `POST /options/{id}/cancel`
- **Query params**: `next` (optional, string: URL path to redirect to)
- **Body**: None
- **Response**: HTTP 302 redirect to `next` (or `/` if not provided)
- **Error**: HTTP 409 if option not found or not in pending/approved status

## 6. Edge Cases

- **No approved items**: Show empty state with "No approved content" message
- **Cancel from approved page**: Redirect back to `/approved` so user stays on the approved page
- **Cancel from dashboard**: Redirect back to `/` (existing behavior preserved)
- **Platform filter with no results**: Show empty state with platform-specific message
- **Concurrent cancel**: Two users cancelling the same item — second gets HTTP 409 (acceptable)
- **Referer not available**: If `next` is not provided, fall back to `/`

## 7. Dependencies
- **Existing**: `app/routes.py`, `app/templates/dashboard.html`, `shared/db.py`
- **New**: None

## 8. Testing Requirements

### Unit Tests
- Test `GET /approved` returns 200 with correct template context
- Test `GET /approved?platform=pinterest` filters correctly
- Test cancel with `next=/approved` redirects to `/approved`
- Test cancel of approved item succeeds (status changes to `cancelled`)
- Test cancel of non-approved item returns 409

### Integration Tests
- Approve an item via dashboard, then verify it appears on `/approved`
- Cancel an item from approved page, verify it disappears from `/approved`
- Verify cancelled item appears in history

### Manual Testing
- Navigate to `/approved` — verify list of approved items
- Click "Preview" — verify full preview opens in new tab
- Click "Cancel" — verify item is cancelled and page refreshes
- Use platform filter tabs — verify filtering works
- Verify navigation link is present and active

## 9. Deployment Considerations
- **Migration**: None needed (no schema changes)
- **Rollback**: Revert route and template changes
- **Monitoring**: No new metrics needed
- **Performance**: Approved items are typically few (< 100), query is lightweight
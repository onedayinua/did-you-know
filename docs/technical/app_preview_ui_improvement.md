# app_preview_ui_improvement.md

## 1. Feature Overview

**Purpose**: Redesign the preview page layout to a two-column side-by-side layout (image on the right, content body on the left) and add Approve/Cancel action buttons for pending content items.

**Business Value**:
- Improved visual flow: users can see the preview body (fact, hashtags, metrics) alongside the image for a more natural review experience
- Quicker approval workflow: users can approve or cancel directly from the preview page without returning to the dashboard
- Consistent with modern CMS preview patterns (content + preview side by side)

**Scope**:
- Modify `templates/preview/base.html` — restructure layout from single-column stacked to two-column side-by-side
- Modify `templates/preview/pinterest.html` and `templates/preview/instagram.html` — inherit the new layout (no structural changes needed, content block remains the same)
- Add Approve button when `option.status == 'pending'`
- Add Cancel button when `option.status in ('pending', 'approved')`
- Reuse existing `POST /options/{id}/approve` and `POST /options/{id}/cancel` endpoints (no new API endpoints needed)
- Use AJAX (fetch) for Approve/Cancel to avoid full-page redirect — show inline status message and update button visibility

**Success Criteria**:
- Preview page renders image on the right side, content body on the left side
- Both image and body are vertically aligned (top-aligned)
- When `option.status == 'pending'`, an "Approve" (green) and "Cancel" (red) button are visible in the actions section
- When `option.status == 'approved'`, only the "Cancel" button is visible (along with existing Post to Pinterest / Mark as Posted buttons for Pinterest)
- When `option.status == 'posted'` or `'cancelled'`, no Approve/Cancel buttons are shown
- Approve action calls `POST /options/{id}/approve`, on success updates the status badges and buttons via DOM without full page reload
- Cancel action calls `POST /options/{id}/cancel`, on success updates status badges and hides buttons
- Responsive: on narrow screens (< 768px), layout collapses to stacked (image below content)

## 2. Service Ownership

**Primary Service**: `app` (FastAPI routes + Jinja2 templates)

**Dependent Services**: None

**Interface Changes**:

| Change | Type | Description |
|--------|------|-------------|
| `templates/preview/base.html` | Template restructure | Convert from stacked to two-column layout; add Approve/Cancel buttons + JS |
| `templates/preview/pinterest.html` | Template change | No structural changes — inherits new base layout via `{% extends %}` |
| `templates/preview/instagram.html` | Template change | Same as pinterest.html — inherits new layout |

**No new API endpoints**:
- `POST /options/{id}/approve` — already exists (line 233 in routes.py)
- `POST /options/{id}/cancel` — already exists (line 260 in routes.py)

## 3. Detailed Implementation

### 3.1 Template: `templates/preview/base.html`

#### 3.1.1 Layout Restructure

Replace the current single-column `.preview-container` layout:

**Current structure (simplified)**:
```
.preview-container (max-width: 600px)
  .preview-image (100% width, stacked on top)
  .preview-body (below image, padding: 24px)
```

**New structure**:
```
.preview-container (max-width: 1280px)
  .preview-layout (display: flex, flex-direction: row, gap: 24px)
    .preview-body-wrapper (flex: 1, min-width: 0 — left column)
      .preview-body (content: fact, hashtags, metrics, buttons, back-link)
    .preview-image-wrapper (flex: 0 0 auto, max-width: 400px — right column)
      .preview-image (max-height: 500px, width: 100%, object-fit: contain)
```

**Note**: `.preview-body` is renamed to `.preview-body-wrapper` for the outer container, and the existing `.preview-body` padding/content remains inside it.

#### 3.1.2 CSS Changes

**Add to the `<style>` block** (replace relevant sections):

```css
/* Remove: .preview-container { max-width: 600px; } */
.preview-container {
    max-width: 1280px;
    width: 100%;
    background: #fff;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}

/* New: two-column layout */
.preview-layout {
    display: flex;
    flex-direction: row;
    gap: 0;
    min-height: 400px;
}

.preview-body-wrapper {
    flex: 1;
    min-width: 0;
    padding: 24px;
    order: 1;
}

.preview-image-wrapper {
    flex: 0 0 auto;
    max-width: 400px;
    width: 40%;
    background: #f5f5f5;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    order: 2;
    overflow: hidden;
}

.preview-image {
    width: 100%;
    height: auto;
    display: block;
    max-height: 600px;
    object-fit: contain;
}

/* No image fallback */
.preview-image-placeholder {
    width: 100%;
    height: 300px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ccc;
    font-size: 1.2rem;
    background: #f5f5f5;
}

/* Responsive: stack on narrow screens */
@media (max-width: 767px) {
    .preview-layout {
        flex-direction: column;
    }
    .preview-image-wrapper {
        max-width: 100%;
        width: 100%;
        order: -1; /* image on top when stacked */
    }
    .preview-body-wrapper {
        order: 2;
    }
}
```

**Keep existing styles** for `.preview-body`, `.fact-text`, `.hashtags`, `.metrics`, `.img-title`, `.back-link`, `.btn`, `.btn-primary`, `.regenerate-status`, `.regenerate-error`, and platform-specific overrides as-is.

#### 3.1.3 Approve/Cancel Button Section

Add a new action-buttons section **inside `.preview-body-wrapper`**, before the back-link, after the regenerated-actions section:

```html
{% if option.status == 'pending' or option.status == 'approved' %}
<div class="preview-actions" style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee;">
    <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        {% if option.status == 'pending' %}
        <button id="approve-btn" class="btn btn-primary" onclick="approveOption()">Approve</button>
        {% endif %}
        <button id="cancel-btn" class="btn btn-danger" onclick="cancelOption()">Cancel</button>
        <span id="action-status" class="regenerate-status" style="display: none;"></span>
    </div>
</div>
{% endif %}
```

**Important**: This section must appear **after** both the `{% if option.status == 'pending' %}` regenerated-actions block and the `{% if option.status == 'approved' and option.platform == 'pinterest' %}` preview-actions block.

#### 3.1.4 Approve/Cancel JavaScript

Add to the existing `<script>` block at the bottom of `base.html` (after the existing regenerate scripts and Pinterest posting scripts):

```javascript
// ============================================================
// Approve / Cancel Actions
// ============================================================
async function approveOption() {
    const btn = document.getElementById('approve-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const statusEl = document.getElementById('action-status');

    btn.disabled = true;
    cancelBtn.disabled = true;
    statusEl.style.display = 'inline';
    statusEl.innerText = 'Approving...';

    try {
        const resp = await fetch('/options/{{ option.id }}/approve', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.detail || 'Failed to approve');
        }
        statusEl.innerText = 'Approved! Refreshing...';
        setTimeout(() => location.reload(), 1000);
    } catch (err) {
        statusEl.innerText = 'Error: ' + err.message;
        statusEl.style.color = '#e74c3c';
        btn.disabled = false;
        cancelBtn.disabled = false;
    }
}

async function cancelOption() {
    const btn = document.getElementById('approve-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const statusEl = document.getElementById('action-status');

    if (btn) btn.disabled = true;
    cancelBtn.disabled = true;
    statusEl.style.display = 'inline';
    statusEl.innerText = 'Cancelling...';

    try {
        const resp = await fetch('/options/{{ option.id }}/cancel', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.detail || 'Failed to cancel');
        }
        statusEl.innerText = 'Cancelled! Refreshing...';
        setTimeout(() => location.reload(), 1000);
    } catch (err) {
        statusEl.innerText = 'Error: ' + err.message;
        statusEl.style.color = '#e74c3c';
        if (btn) btn.disabled = false;
        cancelBtn.disabled = false;
    }
}
```

#### 3.1.5 HTML Structure (base.html)

**Current HTML `body` structure**:
```html
<div class="preview-container">
    {% if option.image_path %}
        <img class="preview-image" src="/images/{{ option.image_path }}" ...>
    {% else %}
        <div class="preview-image" style="...">No Image Available</div>
    {% endif %}
    <div class="preview-body">
        {% block content %}{% endblock %}
        ... (img_title, metrics, regenerate actions, pinterest actions, back-link)
    </div>
</div>
```

**New HTML `body` structure**:
```html
<div class="preview-container">
    <div class="preview-layout">
        <div class="preview-body-wrapper">
            <div class="preview-body">
                {% block content %}{% endblock %}
                {% if option.img_title %}...{% endif %}
                {% if validation_results %}...{% endif %}
                {% if option.status == 'pending' %}... (regenerate actions) ...{% endif %}
                {% if option.status == 'approved' and option.platform == 'pinterest' %}
                    ... (post to pinterest actions) ...
                {% endif %}
                {% if option.status == 'pending' or option.status == 'approved' %}
                    <!-- Approve / Cancel buttons (new) -->
                {% endif %}
                <a href="/" class="back-link">&larr; Back to Dashboard</a>
            </div>
        </div>
        <div class="preview-image-wrapper">
            {% if option.image_path %}
                <img class="preview-image" src="/images/{{ option.image_path }}" alt="{{ option.theme }}">
            {% else %}
                <div class="preview-image-placeholder">No Image Available</div>
            {% endif %}
        </div>
    </div>
</div>
```

### 3.2 Child Templates

No changes needed in `templates/preview/pinterest.html` or `templates/preview/instagram.html`. They extend `base.html` and only override the `{% block content %}` and `{% block title %}`. The new layout, buttons, and JS are in the base template.

The platform-specific `{% block extra_styles %}` styles (`.pinterest-image { max-height: 600px; }` / `.instagram-image { max-height: 500px; }`) should be updated to target `.preview-image` instead, or simply removed since the base now styles `.preview-image` with `max-height: 600px; object-fit: contain;`.

**Update `pinterest.html`**: Remove or update the extra_styles block — the base template now handles image sizing. The `.pinterest-image` class no longer applies.
**Update `instagram.html`**: Same as pinterest.html.

### 3.3 State Management

| Status | Approve button | Cancel button | Pinterest buttons | Regenerate buttons |
|--------|---------------|---------------|-------------------|-------------------|
| pending | ✅ Visible | ✅ Visible | ❌ Hidden | ✅ Visible |
| approved | ❌ Hidden | ✅ Visible | ✅ Visible (pinterest only) | ❌ Hidden |
| posted | ❌ Hidden | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| cancelled | ❌ Hidden | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| expired | ❌ Hidden | ❌ Hidden | ❌ Hidden | ❌ Hidden |

### 3.4 Route Changes

**No changes needed** to `app/routes.py`. The existing endpoints are reused:
- `POST /options/{id}/approve` returns a `RedirectResponse(url="/", status_code=302)` by default
- `POST /options/{id}/cancel` returns a `RedirectResponse(url=next, status_code=302)` by default

**Important**: In the current implementation, both endpoints return redirects (302). For the AJAX approach in the preview page, the `fetch` call follows the redirect automatically — the browser follows the 302 to the dashboard, but since `fetch` follows redirects by default, it will receive the dashboard HTML (status 200). The current JS implementation detects the redirect via status code — the redirect response has `status=302` and `resp.ok` depends on the final destination.

**Alternative approach (recommended)**: Accept `Accept: application/json` header in the endpoints to return JSON responses instead of redirects. This requires a small change to `routes.py`:

```python
@router.post("/options/{id}/approve")
async def approve_option(id: int, request: Request):
    """Approve a content option."""
    # ... existing logic ...
    if request.headers.get("accept") == "application/json":
        return {"status": "ok", "message": "Content option approved"}
    return RedirectResponse(url="/", status_code=302)
```

This change is backward-compatible — the dashboard uses form submits (no JSON accept header), so it still gets the redirect. The preview page sends `Accept: application/json`, so it gets a JSON response.

## 4. Error Handling

### Expected Failures

| Failure | Scenario | Handling |
|---------|----------|----------|
| Option already approved | User clicks Approve, status changed before request | 409 response — show error inline, reload |
| Option already cancelled | User clicks Cancel, status changed before request | 409 response — show error inline, reload |
| Option not found | Deleted between page load and action | 404 response — show error inline |
| Network error | Fetch fails (offline, server down) | Catch error, show message in status element |
| Double-click Approve | User clicks quickly twice | First click disables button; second click is no-op |

### Error Responses (from server)

All reused endpoints return:
```json
{"detail": "<human-readable message>"}
```

### Error Display

Errors are shown inline in the `#action-status` span with red text (`color: #e74c3c`). The buttons are re-enabled so the user can retry.

## 5. Input/Output Specifications

### No new endpoints

Existing endpoints used:
- `POST /options/{id}/approve` — path param `id: int`
- `POST /options/{id}/cancel` — query param `next: str = "/"` (optional)

### Template Context

No new context variables. Existing context `{"option": option, "config": config, "validation_results": validation_results}` is sufficient.

## 6. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| No image (`image_path` is None) | Preview image wrapper shows "No Image Available" placeholder div (300px height) |
| Very long fact text | Content column scrolls naturally; image column stays at its max width |
| Very tall image | Image constrained by `max-height: 600px; object-fit: contain` — no layout break |
| Small screen (< 768px) | Layout collapses to stacked: image on top, content below |
| Status changes between page load and action | Server returns 409; JS catches and displays error, suggests user reload |
| User on slow network | Buttons show "Approving..." / "Cancelling..." text; user knows action is in progress |
| Both Approve and Cancel clicked rapidly | First click disables both buttons; second click is no-op |
| Option is Instagram (not Pinterest) | Approve/Cancel still show (when pending/approved). Pinterest-specific buttons do not show |
| User navigates back after approve/cancel | Page shows new state (via reload) |

## 7. Dependencies

### External Services
- None

### Internal Services
- `app/routes.py` — `POST /options/{id}/approve` and `POST /options/{id}/cancel` endpoints (already exist)

### Templates Modified
- `app/templates/preview/base.html` — major restructure
- `app/templates/preview/pinterest.html` — minor: update/remove `extra_styles` block for image class
- `app/templates/preview/instagram.html` — minor: update/remove `extra_styles` block for image class

### Configuration
- No new environment variables

## 8. Testing Requirements

### Unit Tests (in `tests/test_routes.py`)

Add to the existing `TestPreviewButtons` class or create a new `TestPreviewUI` class:

| Test | Description |
|------|-------------|
| `test_preview_layout_has_two_columns` | `GET /preview/1` with pending option → HTML contains `.preview-layout`, `.preview-body-wrapper`, `.preview-image-wrapper` classes |
| `test_preview_shows_approve_for_pending` | Pending option → "Approve" button present in HTML |
| `test_preview_shows_cancel_for_pending` | Pending option → "Cancel" button present in HTML |
| `test_preview_shows_cancel_for_approved` | Approved option → "Cancel" button present, "Approve" button absent |
| `test_preview_hides_approve_cancel_for_posted` | Posted option → neither "Approve" nor "Cancel" present |
| `test_preview_hides_approve_cancel_for_cancelled` | Cancelled option → neither "Approve" nor "Cancel" present |
| `test_preview_image_on_right_side` | Verify HTML order: `.preview-body-wrapper` appears before `.preview-image-wrapper` in the DOM (check element order) |

### Existing Tests to Verify Still Pass

- `test_preview_shows_buttons_for_approved` — should still pass (Post to Pinterest / Mark as Posted buttons still present)
- `test_preview_hides_buttons_for_pending` — should still pass (no Pinterest buttons for pending)
- `test_preview_hides_buttons_for_posted` — should still pass
- `test_preview_hides_buttons_for_instagram` — should still pass

### Manual Test Checklist

- [ ] Preview page shows two-column layout with image on right for both Pinterest and Instagram
- [ ] On mobile viewport (< 768px), layout stacks vertically with image on top
- [ ] Pending option shows Approve (green) and Cancel (red) buttons
- [ ] Approved option shows Cancel button only (plus Pinterest buttons for pinterest platform)
- [ ] Posted/cancelled options show no Approve/Cancel buttons
- [ ] Clicking Approve calls `POST /options/{id}/approve`, shows "Approved!" and reloads
- [ ] Clicking Cancel calls `POST /options/{id}/cancel`, shows "Cancelled!" and reloads
- [ ] Error responses (409, 404) show inline error message, buttons re-enabled
- [ ] Image is constrained (max-height, object-fit: contain) and does not overflow

## 9. Deployment Considerations

### Migration Scripts
**None needed.** No database changes.

### Rollback Strategy
1. Revert `templates/preview/base.html` to previous single-column layout
2. Revert `templates/preview/pinterest.html` and `templates/preview/instagram.html` if extra_styles were changed
3. No data impact — all state changes go through existing API endpoints

### Monitoring
- No new metrics needed
- Existing `logger.info("Approved content option id=%d", id)` and `logger.info("Cancelled content option id=%d", id)` already capture approval/cancellation events

### Performance Impact
- None. Template rendering is unchanged in complexity. The approve/cancel endpoints are simple single-row updates.
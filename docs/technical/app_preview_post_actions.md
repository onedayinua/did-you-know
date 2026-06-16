# app_preview_post_actions.md

## 1. Feature Overview

**Purpose**: Allow users to either (a) post approved content to Pinterest via Chrome extension, or (b) mark content as posted manually (moving it to the `posts` table) directly from the preview page.

**Business Value**: Enables a human-in-the-loop workflow where the user can trigger the Pinterest Chrome extension to manually create a pin (with pre-filled data), or bypass the extension and simply record that the post was made. This closes the gap between content approval and the actual posting action.

**Scope**:
- Add two action buttons on the preview page when `option.status == 'approved'`
- "Post to Pinterest" button triggers the `sendPinToExtension` function from `pinterest-uploader-extension/inject.js`
- "Mark as Posted" button calls a new POST endpoint that creates a `posts` record and updates `content_options.status` to `'posted'`
- Both buttons present only for `pinterest` platform (since `sendPinToExtension` is Pinterest-specific)

**Success Criteria**:
- Approved content on the preview page shows "Post to Pinterest" and "Mark as Posted" buttons
- Clicking "Post to Pinterest" calls `sendPinToExtension` with correct title, description, URL, and image base64
- Clicking "Mark as Posted" creates a `posts` record with `status='success'` and updates `content_options.status` to `'posted'`
- After either action, the preview page reflects the new state (buttons disappear / status shown)

## 2. Service Ownership

**Primary Service**: `app` (FastAPI routes + Jinja2 templates)

**Dependent Services**: None (all changes are within the app layer)

**Interface Changes**:

| Change | Type | Description |
|--------|------|-------------|
| `POST /options/{id}/mark-posted` | New API endpoint | Creates `posts` record, sets `content_options.status = 'posted'` |
| `GET /preview/{id}` | Template change | Pass `status` to template for conditional button display |
| `GET /preview/{id}/{platform}` | Template change | Same as above |
| `templates/preview/base.html` | Template change | Add buttons block in preview body |
| `templates/preview/pinterest.html` | Template change | Add button rendering + `sendPinToExtension` JS invocation |

## 3. Detailed Implementation

### 3.1 Database Changes

**No schema changes needed.** The existing `posts` table and `content_options.status` column already support this flow. Existing values:
- `content_options.status` values: `'pending'`, `'approved'`, `'posted'`, `'expired'`, `'cancelled'`
- `posts.status` values: `'pending'`, `'success'`, `'failed'`

### 3.2 New API Endpoint

```
POST /options/{id}/mark-posted
```

**Request**: No body (content_option_id from URL path)

**Response**:
- **200**: JSON `{"status": "ok", "message": "Post marked as posted", "post_id": <int>}`
- **404**: `{"detail": "Content option not found"}`
- **409**: `{"detail": "Option not found or not in approved status"}` — if status is not `'approved'`

**Business Logic** (pseudocode):
```
1. FETCH content_option WHERE id = $id AND status = 'approved'
2. IF not found, raise 404/409
3. BEGIN transaction:
   a. INSERT INTO posts (content_option_id, platform, image_path, status)
      VALUES ($id, option.platform, option.image_path, 'success')
   b. UPDATE content_options SET status = 'posted', updated_at = NOW() WHERE id = $id
4. COMMIT
5. Return 200 with post_id
```

**Implementation location**: Add to `app/routes.py` as a new async handler in the "Actions" section.

### 3.3 Template Changes (preview/base.html)

**Add a buttons section** in the preview-body, after the content block and before the back-link. This section is conditionally rendered only when `option.status == 'approved'` and `option.platform == 'pinterest'`.

The buttons should appear as a row with two buttons:

1. **"Post to Pinterest"** (green, `btn-primary` style)
   - Renders as `<button>` with an `onclick` handler that calls `sendPinToExtension(...)`
   - Inline JS loads the image as base64, then calls the extension

2. **"Mark as Posted"** (blue, accent style)
   - Renders as a form that submits `POST /options/{{ option.id }}/mark-posted`
   - On success (200), reload the page to reflect the new status
   - Standard form with `method="post"` and `action="/options/{{ option.id }}/mark-posted"`

### 3.4 JS: sendPinToExtension Integration

The `inject.js` file exposes `sendPinToExtension(title, description, destinationUrl, imageBase64)`. We need to:

1. **Include the `inject.js` code** in the preview page. Since `inject.js` is in the Chrome extension folder (not served by FastAPI), we have two options:
   - **Option A (Recommended)**: Inline the `sendPinToExtension` function directly into the Jinja2 template as a `<script>` block. This avoids cross-origin issues since the extension code is simple and fully self-contained.
   - **Option B**: Serve `inject.js` as a static file from FastAPI by mounting its directory.

   **We will use Option A** — copy the `sendPinToExtension` function body into an inline `<script>` tag in `preview/base.html`. The function is small (31 lines) and has no external dependencies. The `EXTENSION_ID` placeholder will be configurable via an environment variable `PINTEREST_EXTENSION_ID` with a sensible default (the current placeholder).

2. **Fetch the image as base64** before calling the function. Use a helper JS function:

```javascript
async function fetchImageAsBase64(imageUrl) {
    const response = await fetch(imageUrl);
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}
```

3. **Wire the "Post to Pinterest" button click**:

```html
<button class="btn btn-primary" onclick="postToPinterest()">Post to Pinterest</button>

<script>
async function postToPinterest() {
    const imageUrl = '/images/{{ option.image_path }}';
    const title = '{{ option.theme|e }}';
    const description = '{{ option.fact|e }}\n\n{{ option.hashtags|join(" ") }}';
    const destinationUrl = '{{ config.SITE_URL or "https://example.com" }}'; // configurable base URL
    
    try {
        const imageBase64 = await fetchImageAsBase64(imageUrl);
        sendPinToExtension(title, description, destinationUrl, imageBase64);
    } catch (err) {
        alert('Failed to load image: ' + err.message);
    }
}
</script>
```

### 3.4 State Management

- **Before action**: `content_options.status = 'approved'`, buttons visible
- **After "Post to Pinterest"**: No DB change (extension handles posting). User must click "Mark as Posted" separately after successful post.
- **After "Mark as Posted"**: `content_options.status = 'posted'`, `posts` record created with `status = 'success'`. Page should reload to reflect — buttons disappear because `status` is no longer `'approved'`.

## 4. Error Handling

### Expected Failures — "Post to Pinterest"

| Failure | Handling |
|---------|----------|
| Chrome extension not installed | `chrome.runtime.lastError` is caught in `sendPinToExtension`, shows alert |
| Image fetch fails (404) | `fetchImageAsBase64` throws, caught in `postToPinterest`, shows alert |
| Extension ID mismatch | Same as extension not installed — alert shown |

### Expected Failures — "Mark as Posted"

| HTTP Status | Condition | Response Body |
|-------------|-----------|---------------|
| 404 | `id` not found in `content_options` | `{"detail": "Content option not found"}` |
| 409 | `status` is not `'approved'` | `{"detail": "Option not found or not in approved status"}` |
| 500 | DB transaction failure (insert/update) | Standard FastAPI 500 |

### Error Responses

All follow the existing pattern in `app/routes.py`:
```json
{"detail": "<human-readable message>"}
```

### Logging Requirements

- `logger.info("Marked option %d as posted, post_id=%d", option_id, post_id)` — on success
- `logger.warning("Mark-posted failed for option %d: %s", option_id, reason)` — on 409
- `logger.error("Mark-posted transaction failed for option %d: %s", option_id, error)` — on DB error
- No logging for "Post to Pinterest" (client-side only)

## 5. Input/Output Specifications

### POST /options/{id}/mark-posted

**Input**:
- Path param: `id` — integer, 1 to 2^31 - 1

**Output (200)**:
```json
{
    "status": "ok",
    "message": "Post marked as posted",
    "post_id": 123
}
```

**Output (404)**:
```json
{
    "detail": "Content option not found"
}
```

**Output (409)**:
```json
{
    "detail": "Option not found or not in approved status"
}
```

### Template Context Additions

The preview template context already provides `{"option": option}`. No additional context variables needed — `option.status` and `option.platform` are used directly.

## 6. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Option status changes between page load and button click | "Mark as Posted" returns 409; page should be reloaded |
| User double-clicks "Mark as Posted" | Second request returns 409 (status no longer `'approved'`) |
| Image file missing from disk | `fetchImageAsBase64` gets a 404; user sees alert, can still use "Mark as Posted" |
| Image is very large (>10MB) | `fetchImageAsBase64` may fail or be slow; catch error, show alert |
| Non-Pinterest platform preview | Buttons hidden (only show for `platform == 'pinterest'`) |
| No `PINTEREST_EXTENSION_ID` env var | `sendPinToExtension` uses placeholder `"PASTE_YOUR_EXTENSION_ID_HERE"`; user sees alert |
| Concurrent mark-posted requests | First request succeeds; second returns 409 (idempotent via status check) |

## 7. Dependencies

### External Services
- Chrome Extension (user-side, not server): `pinterest-uploader-extension/`
  - Files: `inject.js` (for `sendPinToExtension`)
  - Files: `content.js` (handles `prefill` action in the extension)

### Internal Services
- `shared/db.py` — `fetch_one` and `execute` for DB operations

### Configuration
- **New env var**: `PINTEREST_EXTENSION_ID` — string, Chrome extension ID (optional, defaults to `"PASTE_YOUR_EXTENSION_ID_HERE"`)
- **Existing**: `SITE_URL` (optional, for destination URL in pin) — if not set, uses `"https://example.com"`

### No new libraries or frameworks needed

## 8. Testing Requirements

### Unit Tests

| Test | Description |
|------|-------------|
| `test_mark_posted_success` | Call `POST /options/{id}/mark-posted` with valid approved option → returns 200, creates post record, updates status to `posted` |
| `test_mark_posted_not_found` | Call with non-existent id → returns 404 |
| `test_mark_posted_not_approved` | Call with option in `pending` status → returns 409 |
| `test_mark_posted_already_posted` | Call with option already `posted` → returns 409 |
| `test_mark_posted_cancelled` | Call with cancelled option → returns 409 |
| `test_preview_shows_buttons_for_approved` | GET `/preview/{id}` with approved pinterest option → buttons present in HTML |
| `test_preview_hides_buttons_for_non_approved` | GET `/preview/{id}` with pending option → buttons absent |
| `test_preview_hides_buttons_for_instagram` | GET `/preview/{id}/instagram` with approved option → buttons absent |

### Integration Tests
- Full flow: approve option → preview page shows buttons → mark as posted → preview page shows no buttons → history page shows the post

### No performance or security tests needed (simple CRUD + client-side JS)

## 9. Deployment Considerations

### Migration Scripts
**None needed.** Existing schema supports this.

### Rollback Strategy
1. Revert `app/routes.py` — remove the `mark_posted` endpoint
2. Revert `templates/preview/base.html` and `templates/preview/pinterest.html` — remove buttons and JS
3. Any `posts` records created during the feature's lifetime remain valid — no data loss

### Monitoring
- Add log line `logger.info("Marked option %d as posted, post_id=%d", ...)` for tracking
- No new metrics or dashboards needed

### Performance Impact
- Minimal: one `SELECT`, one `INSERT`, one `UPDATE` per "Mark as Posted" action
- `fetchImageAsBase64` runs client-side — no server load
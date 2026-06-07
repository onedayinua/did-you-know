# app_image_path_mismatch.md

## 1. Feature Overview
**Purpose**: Fix broken image display in the dashboard and preview pages
**Business Value**: Users cannot see generated images in the dashboard or preview pages, making the content management UI unusable
**Scope**: Fix the URL path mismatch between stored image paths and FastAPI static file mount
**Success Criteria**: Images render correctly in dashboard (`/`) and preview (`/preview/{id}`) pages

## 2. Service Ownership
**Primary Service**: `app` (FastAPI web application)
**Affected Components**:
- `app/main.py` — Static file mount configuration
- `modules/visual_generator.py` — Image path storage logic
- `app/templates/dashboard.html` — Image src attribute in template
- `app/templates/preview/base.html` — Image src attribute in template
- `tests/test_routes.py` — Mock data for tests

## 3. Root Cause Analysis

### The Mismatch
| Component | Path | Example |
|-----------|------|---------|
| **Stored in DB** (`image_path`) | `data/images/{filename}` | `data/images/batch_20260607_083321_0c97a3_24.png` |
| **Rendered in template** | `src="/{{ image_path }}"` | `src="/data/images/batch_20260607_083321_0c97a3_24.png"` |
| **FastAPI mount** | `/images` → `data/images/` | Serves at `/images/{filename}` |
| **Browser requests** | `/data/images/{filename}` | ❌ 404 Not Found |
| **Should request** | `/images/{filename}` | ✅ 200 OK |

### Why It Happened
- `visual_generator.py` line 233: `filepath = os.path.join(self._images_dir, filename)` produces `data/images/batch_xxx.png`
- This full relative path is stored in the database (line 261: `UPDATE content_options SET image_path = $1`)
- Templates render `src="/{{ option.image_path }}"` which becomes `/data/images/batch_xxx.png`
- But `main.py` line 84 mounts at `/images`, not `/data/images`

## 4. Detailed Implementation

### 4.1 Change `modules/visual_generator.py` — Store only filename

**File**: `modules/visual_generator.py`
**Lines**: 232-244 (the `_generate_and_save` method)

**Current behavior**:
```python
filename = f"{option.batch_id}_{option.id}.png"
filepath = os.path.join(self._images_dir, filename)  # "data/images/batch_xxx.png"
# ... writes to filepath ...
return filepath  # Returns "data/images/batch_xxx.png"
```

**New behavior**:
```python
filename = f"{option.batch_id}_{option.id}.png"
filepath = os.path.join(self._images_dir, filename)  # "data/images/batch_xxx.png"
# ... writes to filepath (unchanged) ...
return filename  # Return just "batch_xxx.png" instead of full path
```

**Change**: On line 244, change `return filepath` to `return filename`.

### 4.2 Change `app/templates/dashboard.html` — Fix image src URL

**File**: `app/templates/dashboard.html`
**Lines**: 178 and 202

**Current**:
```html
<img class="card-image" src="/{{ item.image_path }}" alt="{{ item.theme }}">
<img class="card-image" src="/{{ option.image_path }}" alt="{{ option.theme }}">
```

**New**:
```html
<img class="card-image" src="/images/{{ item.image_path }}" alt="{{ item.theme }}">
<img class="card-image" src="/images/{{ option.image_path }}" alt="{{ option.theme }}">
```

### 4.3 Change `app/templates/preview/base.html` — Fix image src URL

**File**: `app/templates/preview/base.html`
**Line**: 75

**Current**:
```html
<img class="preview-image" src="/{{ option.image_path }}" alt="{{ option.theme }}">
```

**New**:
```html
<img class="preview-image" src="/images/{{ option.image_path }}" alt="{{ option.theme }}">
```

### 4.4 Change `tests/test_routes.py` — Update mock data

**File**: `tests/test_routes.py`
**Line**: 70

**Current**:
```python
"image_path": "data/images/test.png",
```

**New**:
```python
"image_path": "test.png",
```

## 5. Error Handling
- **No image_path**: Templates already handle this with `{% if option.image_path %}` / `{% else %}` showing "No Image" — no changes needed
- **File missing on disk**: FastAPI StaticFiles will return 404 naturally; no custom error handling needed
- **Empty filename**: If `image_path` is empty string, the `{% if %}` check will skip it correctly

## 6. Input/Output Specifications
- **Database column**: `content_options.image_path` — previously stored `data/images/{filename}`, now stores `{filename}` only
- **Existing rows**: Rows already in the database with `data/images/...` prefix will still work because the template now uses `/images/` prefix. The old data will produce URL `/images/data/images/batch_xxx.png` which is wrong. **A data migration is needed** (see section 9).

## 7. Edge Cases
- **Existing database rows**: Rows created before this fix have `image_path` starting with `data/images/`. After the fix, these will produce broken URLs (`/images/data/images/batch_xxx.png`). A migration script must strip the prefix.
- **Concurrent image generation**: If images are being generated while the fix is deployed, some rows may have the old format and some the new. The migration handles this.
- **Rollback**: If reverted, new rows will have just filenames and templates will use `/images/` prefix, which won't match the old mount at `/images` — actually it will still work because `/images/{filename}` is correct regardless.

## 8. Dependencies
- **No new dependencies**
- **No configuration changes**
- **No API changes**

## 9. Deployment Considerations

### 9.1 Data Migration
A migration script must update existing rows to strip the `data/images/` prefix:

```sql
UPDATE content_options
SET image_path = RIGHT(image_path, LENGTH(image_path) - LENGTH('data/images/'))
WHERE image_path LIKE 'data/images/%';
```

This should be run **before** deploying the code changes, so that existing rows are compatible with the new template URLs.

### 9.2 Rollback Strategy
- **Revert code changes** in `visual_generator.py`, templates, and tests
- **No need to revert data** — the migration is one-way but harmless. Old code with `src="/{{ image_path }}"` will work with both `data/images/xxx.png` and `xxx.png` because... actually no, it won't. If we roll back, rows with just `xxx.png` would render as `/xxx.png` which is wrong.
- **Better rollback**: Re-run the migration in reverse:
  ```sql
  UPDATE content_options
  SET image_path = 'data/images/' || image_path
  WHERE image_path NOT LIKE 'data/images/%' AND image_path IS NOT NULL;
  ```

### 9.3 Monitoring
- After deployment, verify dashboard page loads images correctly
- Check browser console for 404 errors on image URLs
- Verify preview pages show images

### 9.4 Performance Impact
- Negligible — only URL string formatting changes, no new I/O or computation

## 10. Testing Requirements

### 10.1 Unit Tests
- Test that `VisualGenerator._generate_and_save()` returns just the filename, not the full path
- Test that the returned filename matches the pattern `{batch_id}_{option_id}.png`

### 10.2 Integration Tests
- Test that the dashboard page renders `<img src="/images/{filename}">` for options with images
- Test that the preview page renders `<img src="/images/{filename}">` for options with images
- Test that options without `image_path` still show "No Image" fallback

### 10.3 Existing Tests
- Update `test_routes.py` mock data to use `"test.png"` instead of `"data/images/test.png"`
- Run existing tests to ensure nothing else breaks

## 11. Tasks

1. **Fix `modules/visual_generator.py`**: Change `return filepath` to `return filename` on line 244
2. **Fix `app/templates/dashboard.html`**: Change `src="/{{ item.image_path }}"` to `src="/images/{{ item.image_path }}"` (lines 178, 202)
3. **Fix `app/templates/preview/base.html`**: Change `src="/{{ option.image_path }}"` to `src="/images/{{ option.image_path }}"` (line 75)
4. **Fix `tests/test_routes.py`**: Change `"image_path": "data/images/test.png"` to `"image_path": "test.png"` (line 70)
5. **Run data migration**: Execute SQL to strip `data/images/` prefix from existing rows
6. **Verify**: Start the app and confirm images load on dashboard and preview pages
# preview_hashtag_display_fix.md

## 1. Feature Overview
**Purpose**: Fix how hashtags are displayed on the preview page and how they are formatted when posted to Pinterest.
**Business Value**: Users currently see hashtags rendered as a raw Python list representation (`[ "# S u s t a i n a b l e E a t i n g " , ... ]`) with spaces between each character. They need each hashtag on its own line, without brackets, commas, or intra-word spaces.
**Scope**: Three Jinja2 template files: `base.html`, `pinterest.html`, `instagram.html`. Also the `postToPinterest()` JavaScript function in `base.html`.
**Success Criteria**:
- Preview page shows each hashtag on its own line (no `[`/`]` brackets, no commas, no intra-word spaces)
- Pinterest pin description uses newline-separated hashtags instead of space-separated

## 2. Service Ownership
**Primary Service**: `app/templates/` (Jinja2 template rendering)
**Dependent Services**: `app/routes.py` (provides `option.hashtags` dict to templates)
**Interface Changes**: No API changes. Only template rendering changes.

## 3. Detailed Implementation

### Files to Modify

#### File 1: `app/templates/preview/base.html`
**Current (line 95)**:
```html
<div class="hashtags">{{ option.hashtags|join(' ') }}</div>
```

**Problem**: `|join(' ')` renders as `#SustainableEating #LocalIngredients` but the user reports seeing `[ " # S u s t a i n a b l ... ]` — this suggests `option.hashtags` is being treated as a string (not a list) in some data path, causing `list()` on a string to split into individual characters.

**Fix**: Replace with a `{% for %}` loop that renders each hashtag on its own line:
```html
<div class="hashtags">{% for hashtag in option.hashtags %}{{ hashtag }}{% if not loop.last %}<br>{% endif %}{% endfor %}</div>
```

This ensures:
- Each hashtag is rendered individually (not joined into a single string)
- No `[` or `]` brackets appear
- No commas between hashtags
- Each hashtag starts on a new line (via `<br>`)

**Current (line 142)** — Pinterest description in `postToPinterest()`:
```javascript
const description = '{{ option.fact|e }}\n\n{{ option.hashtags|join(" ") }}';
```

**Problem**: `|join(" ")` joins with spaces, producing `#SustainableEating #LocalIngredients`. The user wants each on its own line.

**Fix**: Use a `{% for %}` loop with `\n` newlines:
```javascript
const description = '{{ option.fact|e }}\n\n{% for hashtag in option.hashtags %}{{ hashtag }}{% if not loop.last %}\n{% endif %}{% endfor %}';
```

#### File 2: `app/templates/preview/pinterest.html`
**Current (line 24)**:
```html
<div class="hashtags">{{ option.hashtags|join(' ') }}</div>
```

**Fix**: Same as `base.html`:
```html
<div class="hashtags">{% for hashtag in option.hashtags %}{{ hashtag }}{% if not loop.last %}<br>{% endif %}{% endfor %}</div>
```

#### File 3: `app/templates/preview/instagram.html`
**Current (line 24)**:
```html
<div class="hashtags">{{ option.hashtags|join(' ') }}</div>
```

**Fix**: Same as `base.html`:
```html
<div class="hashtags">{% for hashtag in option.hashtags %}{{ hashtag }}{% if not loop.last %}<br>{% endif %}{% endfor %}</div>
```

### CSS Update (optional)
In `base.html` (lines 38-43), the `.hashtags` class has `line-height: 1.8` which is fine for `<br>`-separated lines. No change needed.

## 4. Error Handling
- **Empty hashtags list**: The `{% for %}` loop renders nothing when `option.hashtags` is empty — this is correct behavior.
- **Single hashtag**: `loop.last` is `True` on first iteration, so no `<br>` is appended — correct.
- **None/undefined hashtags**: If `option.hashtags` is `None`, Jinja2's `{% for %}` on `None` will error. The `_row_to_dict` in `routes.py` ensures it's always a list (line 611).

## 5. Input/Output Specifications
**Input**: `option.hashtags` — a Python list of strings like `["#SustainableEating", "#LocalIngredients"]`
**Output**: HTML with each hashtag on its own line, separated by `<br>` tags.

## 6. Edge Cases
- **Empty list**: No hashtags rendered — `<div class="hashtags"></div>` (empty div)
- **Single hashtag**: Rendered as `<div class="hashtags">#SingleTag</div>` (no `<br>`)
- **Many hashtags (10-30)**: Each on its own line, `<br>` between each
- **Hashtags with special characters**: `{{ hashtag }}` in Jinja2 auto-escapes HTML — safe

## 7. Dependencies
- Jinja2 template engine (built into FastAPI)
- No new dependencies

## 8. Testing Requirements
- **Visual test**: Load preview page and verify each hashtag appears on its own line
- **Pinterest test**: Click "Post to Pinterest" and verify the description contains newline-separated hashtags
- **Edge case test**: Test with 0, 1, and 10+ hashtags

## 9. Deployment Considerations
- **No migration needed**: Template-only change
- **No rollback risk**: Templates are stateless — just revert the file changes
- **No performance impact**: `{% for %}` loop over a small list (5-30 items) is negligible
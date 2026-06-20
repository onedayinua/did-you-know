# config_model_consistency.md

## 1. Feature Overview
**Purpose**: Resolve a configuration inconsistency where the image generation model is defined in two places (`content_template.yaml` as `image_model` and `platforms.yaml` as `visual.model`), but only `platforms.yaml` -> `visual.model` is actually used at runtime. The `image_model` field in `content_template.yaml` is dead code that misleads developers.

**Business Value**: Eliminate confusion about which config value controls image generation. Ensure a single source of truth for model configuration.

**Scope**:
- Remove `image_model` from `content_template.yaml`
- Remove the dead `self._image_model` field from `ContentGenerator`
- Update `ContentGenerator` docstring to remove reference to `image_model`
- Update `VisualGenerator` docstring default reference from `"dall-e-3"` to match actual default

**Success Criteria**:
- `image_model` no longer exists in `content_template.yaml`
- `ContentGenerator` no longer reads or stores `image_model`
- All existing tests pass without modification
- Runtime behavior is unchanged (image generation still uses `platforms.yaml` -> `visual.model`)

## 2. Service Ownership
**Primary Service**: config (configuration files)
**Affected Modules**:
- `modules/content_generator.py` — remove dead code
- `config/content_template.yaml` — remove unused field
- `modules/visual_generator.py` — minor docstring update

**Interface Changes**: None. No public API, message format, or database schema changes.

## 3. Detailed Implementation

### 3.1 `config/content_template.yaml` (line 57-58)
Remove the two lines:
```yaml
# AI model selection
text_model: "openai/gpt-4o-mini"
image_model: "openai/dall-e-3"
```

Replace with a single line:
```yaml
# AI model selection (text generation only; image model is in platforms.yaml -> visual.model)
text_model: "openai/gpt-4o-mini"
```

### 3.2 `modules/content_generator.py` (line 51)
Remove the line:
```python
self._image_model: str = config.get("image_model", "openai/dall-e-3")
```

### 3.3 `modules/content_generator.py` (docstring, lines 35-38)
Update the docstring's `config` parameter description. Remove `image_model` from the list of expected keys. Current text:
```
config: The ``content_template.yaml`` config dict. Expected keys:
    ``text_prompt``, ``image_prompt``, ``platforms``, ``variations``,
    ``queue.max_pending``, ``queue.expire_days``,
    ``queue.cleanup_on_generate``.
```
(Note: `image_model` is already NOT listed in the docstring, so no change needed here.)

### 3.4 `modules/visual_generator.py` (docstring, line 46)
Update the default value reference from `"dall-e-3"` to the actual default `"black-forest-labs/flux.2-klein-4b"`:
```
Current: ``visual.model`` (default ``"dall-e-3"``)
New:     ``visual.model`` (default ``"black-forest-labs/flux.2-klein-4b"``)
```

## 4. Error Handling
No new error handling needed. This is a cleanup of dead code. No runtime behavior changes.

## 5. Input/Output Specifications
No changes to inputs or outputs. All existing interfaces remain identical.

## 6. Edge Cases
- **If someone was relying on `content_template.yaml` -> `image_model`**: This field was never read at runtime, so no code could have depended on it. No breakage possible.
- **If `platforms.yaml` is missing `visual.model`**: The `VisualGenerator` already has a fallback default (`"openai/dall-e-3"`). This behavior is unchanged. Consider updating this default to match the actual configured value (`"black-forest-labs/flux.2-klein-4b"`) as a separate improvement.

## 7. Dependencies
No new dependencies. No external service changes.

## 8. Testing Requirements
- **Unit Tests**: Run existing tests for `ContentGenerator` and `VisualGenerator` to confirm no regressions.
- **No new tests needed**: This is a dead code removal with zero behavioral change.

## 9. Deployment Considerations
- **No migration needed**: No database changes.
- **No rollback risk**: Reverting the config file and code changes restores the previous state with no side effects.
- **No performance impact**: Removing an unused attribute has zero runtime cost.
# content_template_model_config.md

## 1. Feature Overview

**Purpose**: Move hardcoded AI model names (`openai/gpt-4o-mini` for text, `openai/dall-e-3` for image) into YAML config files so they can be changed without code modifications.

**Business Value**: Enables swapping AI models (e.g., switching from `gpt-4o-mini` to `claude-3-haiku` or from `dall-e-3` to a different image model) by editing config files only — no code changes needed.

**Scope**:
- Add `text_model` key to `content_template.yaml`
- Add `image_model` key to `content_template.yaml`
- Update `ThemeAssociator` to read `text_model` from config
- Update `ContentGenerator` to read `text_model` and `image_model` from config
- Update `VisualGenerator` to read `image_model` from config (already reads `model` from `platforms.yaml`)
- Update tests to use config-driven model names

**Not in scope**:
- Changing the `platforms.yaml` `visual.model` key (already exists and works)
- Adding new AI models or providers
- Changing the `OpenRouterClient` method signatures (defaults stay as fallbacks)

**Success Criteria**:
- No hardcoded model strings remain in `modules/theme_associator.py`, `modules/content_generator.py`, or `modules/visual_generator.py`
- All model names are read from config files
- All existing tests pass with updated model references

## 2. Service Ownership

**Primary Service**: `modules/theme_associator.py`, `modules/content_generator.py`, `modules/visual_generator.py`

**Dependent Services**:
- `config/content_template.yaml` — new config keys added
- `config/platforms.yaml` — already has `visual.model` for image model
- `tests/test_theme_associator.py` — update hardcoded model assertions
- `tests/test_content_generator.py` — update hardcoded model assertions
- `tests/test_visual_generator.py` — update hardcoded model assertions
- `tests/test_scheduler.py` — update hardcoded model assertions

**Interface Changes**: None — all changes are internal to module constructors and config parsing.

## 3. Detailed Implementation

### 3.1 Config file changes

**`config/content_template.yaml`** — add at the end:
```yaml
# AI model selection
text_model: "openai/gpt-4o-mini"
image_model: "openai/dall-e-3"
```

**`config/platforms.yaml`** — no changes needed (already has `visual.model: "openai/dall-e-3"`)

### 3.2 ThemeAssociator changes

**File**: `modules/theme_associator.py`

**Current** (line 126):
```python
response = await self._client.generate_text(
    prompt=prompt,
    model="openai/gpt-4o-mini",
    max_tokens=50,
    temperature=0.7,
)
```

**New** — read model from config in `__init__`:
```python
def __init__(self, db_pool, openrouter_client, config):
    ...
    self._prompt_template: str = config.get("theme_prompt", "")
    self._text_model: str = config.get("text_model", "openai/gpt-4o-mini")
    ...
```

Then use it:
```python
response = await self._client.generate_text(
    prompt=prompt,
    model=self._text_model,
    max_tokens=50,
    temperature=0.7,
)
```

### 3.3 ContentGenerator changes

**File**: `modules/content_generator.py`

**Current** (lines 268, 385):
```python
response = await self._client.generate_text(
    prompt=prompt,
    model="openai/gpt-4o-mini",
    ...
)
```

**New** — read models from config in `__init__`:
```python
def __init__(self, db_pool, openrouter_client, config):
    ...
    self._text_model: str = config.get("text_model", "openai/gpt-4o-mini")
    self._image_model: str = config.get("image_model", "openai/dall-e-3")
    ...
```

Then use `self._text_model` in `_generate_text_variations()` and `_generate_image_prompt()`.

### 3.4 VisualGenerator changes

**File**: `modules/visual_generator.py`

**Current** (line 49):
```python
self._model: str = visual_config.get("model", "dall-e-3")
```

**New** — update default to full slug:
```python
self._model: str = visual_config.get("model", "openai/dall-e-3")
```

This is already partially done (the config now has `"openai/dall-e-3"`), but the fallback default should also use the full slug.

### 3.5 Test changes

**`tests/test_theme_associator.py`** (line 122):
- Update assertion to check `self._text_model` or mock config value
- Or update the expected model string if tests use real config

**`tests/test_visual_generator.py`** (lines 36, 316, 524, 547):
- Update `"dall-e-3"` to `"openai/dall-e-3"` in mock configs and assertions

**`tests/test_scheduler.py`** (line 66):
- Update `"dall-e-3"` to `"openai/dall-e-3"` in mock config

## 4. Error Handling

| Failure | Cause | Handling |
|---------|-------|----------|
| Missing `text_model` in config | Config file not updated | Fall back to default `"openai/gpt-4o-mini"` |
| Missing `image_model` in config | Config file not updated | Fall back to default `"openai/dall-e-3"` |
| Invalid model name in config | Typo in config | OpenRouter will return 400; existing error handling applies |

## 5. Input/Output Specifications

No API changes — all changes are internal to module initialization.

## 6. Edge Cases

- **Config file missing keys**: Each module has a fallback default, so missing keys won't crash
- **Empty string in config**: `config.get("text_model", "")` would return `""` — the `OpenRouterClient` will handle this (it passes the model string to the API)
- **Backward compatibility**: Old config files without `text_model`/`image_model` keys will use defaults

## 7. Dependencies

No new dependencies. All changes use existing config parsing patterns.

## 8. Testing Requirements

### Unit Tests
- `test_theme_associator.py`: Update model assertion to match config-driven value
- `test_content_generator.py`: Update model assertions in `_generate_text_variations` and `_generate_image_prompt` tests
- `test_visual_generator.py`: Update `"dall-e-3"` to `"openai/dall-e-3"` in mock configs and assertions
- `test_scheduler.py`: Update `"dall-e-3"` to `"openai/dall-e-3"` in mock config

### Integration Tests
- Run `python -m pytest tests/ -v` — all tests must pass

## 9. Deployment Considerations

- Config files must be updated before or alongside the code changes
- Old configs without `text_model`/`image_model` will use defaults (safe rollback)
- No database migrations needed
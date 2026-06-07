# visual_generator_image_size_config.md

## 1. Feature Overview
**Purpose**: Add an `image_size` config option to control the generation resolution passed to the OpenRouter API, defaulting to `"0.5K"` to keep costs low.
**Business Value**: Users can control image quality vs. cost. The default `"0.5K"` generates smaller, cheaper images. Larger sizes like `"1K"` produce higher quality but cost more.
**Scope**: Add `image_size` to `config/platforms.yaml`, pass it through `VisualGenerator` to `OpenRouterClient.generate_image()`, which sends it in the `image_config` block.
**Success Criteria**: The `image_size` value from config is included in the API request body under `image_config.size`.

## 2. Service Ownership
**Primary Service**: `modules/visual_generator.py` — reads config and passes to client
**Dependent Service**: `shared/openrouter_client.py` — accepts new `size` parameter
**Interface Changes**: `OpenRouterClient.generate_image()` gains an optional `size` parameter

## 3. Detailed Implementation

### 3.1 Add `image_size` to config
**File**: `config/platforms.yaml`
**Change**: Add `image_size: "0.5K"` under the `visual` section:

```yaml
visual:
  model: "black-forest-labs/flux.2-klein-4b"
  style: "food photography, bright, appetizing, clean background"
  image_size: "0.5K"
  dimensions:
    pinterest:
      width: 500
      height: 1000
    instagram:
      width: 1080
      height: 1080
```

### 3.2 Read `image_size` in `VisualGenerator.__init__()`
**File**: `modules/visual_generator.py`
**Change**: Add `self._image_size` after line 55:

```python
self._image_size: str = visual_config.get("image_size", "0.5K")
```

### 3.3 Pass `size` to `generate_image()` in `_generate_and_save()`
**File**: `modules/visual_generator.py`
**Change**: Add `size=self._image_size` to the `generate_image()` call (around line 234):

```python
image_bytes = await self._client.generate_image(
    prompt=option.image_prompt or "",
    model=self._model,
    aspect_ratio=aspect_ratio,
    size=self._image_size,
)
```

### 3.4 Add `size` parameter to `OpenRouterClient.generate_image()`
**File**: `shared/openrouter_client.py`
**Change**: Add `size: str | None = None` parameter, include in `image_config` if provided:

```python
async def generate_image(
    self,
    prompt: str,
    model: str = "openai/dall-e-3",
    aspect_ratio: str = "1:1",
    size: str | None = None,
) -> bytes:
```

And in the body construction (line 219), change:
```python
"image_config": {"aspect_ratio": aspect_ratio},
```
To:
```python
image_config = {"aspect_ratio": aspect_ratio}
if size:
    image_config["size"] = size
body = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "modalities": ["image"],
    "image_config": image_config,
}
```

Also update the docstring to document the new parameter.

### 3.5 Update `VisualGenerator.__init__()` docstring
**File**: `modules/visual_generator.py`
**Change**: Add `visual.image_size` to the documented config keys (line 44-45).

## 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| `image_size` missing from config | Defaults to `"0.5K"` |
| `image_size` is empty string | Treated as not provided — `size` not sent in request |
| Model doesn't support `size` | OpenRouter ignores unknown `image_config` fields gracefully |
| Invalid size value (e.g. `"abc"`) | OpenRouter returns an error → `OpenRouterError` raised → caught by `run()` try/except → option skipped with log |

## 5. Input/Output Specifications

**Config input**:
```yaml
visual:
  image_size: "0.5K"  # string, optional, default "0.5K"
```

**API request change** (when size is provided):
```json
{
  "model": "black-forest-labs/flux.2-klein-4b",
  "messages": [{"role": "user", "content": "..."}],
  "modalities": ["image"],
  "image_config": {
    "aspect_ratio": "2:3",
    "size": "0.5K"
  }
}
```

## 6. Edge Cases

- **No `image_size` in config**: Default `"0.5K"` is used — safe and cheap
- **`image_size: ""`**: Empty string → treated as None → not sent → model uses default
- **Model ignores `size`**: Some models may not support it; OpenRouter silently ignores unknown fields
- **Very large size (e.g. `"4K"`)**: Passed through as-is; cost and generation time increase

## 7. Dependencies
- **No new dependencies**
- **No config structure changes** (new optional key only)

## 8. Testing Requirements

### 8.1 Unit Tests — `test_visual_generator.py`

1. **`test_passes_image_size_to_client`**: Verify that `generate_image()` is called with `size="0.5K"` when config has `image_size`.

2. **`test_default_image_size`**: When config has no `image_size`, verify it defaults to `"0.5K"`.

### 8.2 Unit Tests — `test_openrouter_client.py`

1. **`test_generate_image_with_size`**: Verify that when `size` is provided, it appears in the request body under `image_config.size`.

2. **`test_generate_image_without_size`**: Verify that when `size` is None, the `image_config` does not contain a `size` key.

### 8.3 Existing Tests
- Update `test_passes_correct_parameters` to expect `size` in the call
- All existing tests should continue to pass

## 9. Deployment Considerations
- **No migration needed**
- **No rollback concerns** — adding an optional field is backward-compatible
- **Monitoring**: Log the `size` value in the existing log line for image generation requests
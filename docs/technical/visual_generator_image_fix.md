# visual_generator_image_fix.md — Pass aspect_ratio + output_megapixels to AI

## 1. Feature Overview

**Purpose**: Fix image size mismatch — AI returns 939x704 instead of the configured 500x1000 for Pinterest. The solution is to pass better AI generation hints (`aspect_ratio` + `output_megapixels`) so the model produces images at the correct aspect ratio natively.

**Strategy**: **Hints only, no post-generation resize.** Pillow `resize()` distorts images by stretching. Instead, we trust the AI to produce the right aspect ratio when given proper hints.

**Business Value**: Pinterest requires portrait-oriented images (ideally 2:3 aspect ratio). Currently images come out at arbitrary resolutions.

**Scope**:
- `shared/openrouter_client.py`: Add `output_megapixels` parameter
- `modules/visual_generator.py`: Read new config, pass through to AI
- `config/platforms.yaml`: Add `width`/`height`, `aspect_ratio`, `output_megapixels`
- `pyproject.toml`: No new dependencies needed

**Success Criteria**:
- API request body includes `image_config.aspect_ratio: "2:3"` and `image_config.output_megapixels: 1.0` for Pinterest
- No distorting resize is applied to the generated image

## 2. Service Ownership

| Service | File | Change |
|---------|------|--------|
| OpenRouterClient | `shared/openrouter_client.py` | Add `output_megapixels` param to `generate_image()` |
| VisualGenerator | `modules/visual_generator.py` | Read new config, pass to client |
| Config | `config/platforms.yaml` | Add `width`, `height`, `aspect_ratio`, `output_megapixels` to pinterest |

## 3. Detailed Implementation

### 3.1 Config — `config/platforms.yaml`

```yaml
pinterest:
  width: 500
  height: 1000
  aspect_ratio: "2:3"
  output_megapixels: 1.0
```

- `width`/`height` → for `_get_dimensions()` which derives aspect ratio (backward compat with old format)
- `aspect_ratio` → passed to OpenRouter as AI generation hint (`"2:3"`)
- `output_megapixels` → passed to OpenRouter as AI resolution hint (`1.0`)

### 3.2 `shared/openrouter_client.py` — `output_megapixels` param

**`generate_image()` signature**:
```python
async def generate_image(
    self,
    prompt: str,
    model: str = "openai/dall-e-3",
    aspect_ratio: str = "1:1",
    size: str | None = None,
    output_megapixels: float | None = None,
) -> bytes:
```

**Logic**: After `image_config["size"] = size`:
```python
if output_megapixels is not None:
    image_config["output_megapixels"] = output_megapixels
```

### 3.3 `modules/visual_generator.py`

**`_get_aspect_ratio()`** — Checks for explicit `aspect_ratio` key first, falls back to deriving from width/height, then hardcoded map:
```python
def _get_aspect_ratio(self, platform: str) -> str:
    dims = self._dimensions.get(platform)
    if dims:
        if "aspect_ratio" in dims:
            return dims["aspect_ratio"]
        if dims.get("width") and dims.get("height"):
            from math import gcd
            w, h = dims["width"], dims["height"]
            g = gcd(w, h)
            return f"{w // g}:{h // g}"
    return ASPECT_RATIO_MAP.get(platform, "1:1")
```

**`_get_output_megapixels()`** — New method:
```python
def _get_output_megapixels(self, platform: str) -> float | None:
    dims = self._dimensions.get(platform, {})
    mp = dims.get("output_megapixels")
    if mp is not None and mp > 0:
        return float(mp)
    return None
```

**`_generate_and_save()`** — Passes `output_megapixels` to client, **no resize**:
```python
async def _generate_and_save(self, option, dimensions):
    aspect_ratio = self._get_aspect_ratio(option.platform)
    output_megapixels = self._get_output_megapixels(option.platform)
    image_bytes = await self._client.generate_image(
        prompt=option.image_prompt or "",
        model=self._model,
        aspect_ratio=aspect_ratio,
        size=self._image_size,
        output_megapixels=output_megapixels,
    )
    # NO RESIZE — the image is saved as-is from the AI
    filename = f"{option.batch_id}_{option.id}.png"
    filepath = os.path.join(self._images_dir, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filename
```

## 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| `output_megapixels` not in config | Not sent to API (default AI behavior) |
| `output_megapixels` is 0 or negative | Treated as None — not sent |
| `aspect_ratio` key present | Used directly for AI call |
| `aspect_ratio` missing but width/height present | Derived via GCD |
| Both missing | Falls back to ASPECT_RATIO_MAP |

## 5. Input/Output Specifications

### API Request Body (when all fields present)
```json
{
  "model": "black-forest-labs/flux.2-klein-4b",
  "messages": [{"role": "user", "content": "..."}],
  "modalities": ["image"],
  "image_config": {
    "aspect_ratio": "2:3",
    "size": "0.5K",
    "output_megapixels": 1.0
  }
}
```

## 6. Edge Cases

- **Config has `aspect_ratio` but no `output_megapixels`**: Pass aspect_ratio to AI, skip output_megapixels
- **Config has neither new nor old format**: Fall back to hardcoded 1024x1024, no additional AI hints sent
- **AI ignores hints**: Image may not match the exact aspect ratio — this is an AI model limitation, not fixed by distorting

## 7. Dependencies

No new dependencies. Pillow was added but removed — no post-generation image processing.

## 8. Files Changed

| File | Change Type |
|------|-------------|
| `config/platforms.yaml` | Added `width: 500, height: 1000, aspect_ratio: "2:3", output_megapixels: 1.0` to pinterest |
| `shared/openrouter_client.py` | Added `output_megapixels` param to `generate_image()` |
| `modules/visual_generator.py` | Updated `_get_aspect_ratio()`, added `_get_output_megapixels()`, removed Pillow resize |
| `pyproject.toml` | Pillow dependency removed |
| `tests/test_openrouter_client.py` | Added tests for `output_megapixels` |
| `tests/test_visual_generator.py` | Updated `sample_config`, removed `TestImageResizing`, added `TestOutputMegapixels` |

## 9. Testing

- `test_generate_image_with_output_megapixels` — `output_megapixels=1.0` appears in `image_config`
- `test_generate_image_without_output_megapixels` — no key in `image_config` when not passed
- `test_returns_pinterest_megapixels` — `_get_output_megapixels("pinterest")` returns `1.0`
- `test_returns_none_when_not_configured` — unknown platform returns `None`
- `test_returns_none_when_zero` — config with `0` returns `None`
- `test_passes_correct_parameters` — `generate_image` called with `output_megapixels=1.0`
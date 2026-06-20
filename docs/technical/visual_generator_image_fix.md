# visual_generator_image_fix.md — Pass aspect_ratio + output_megapixels + Pillow resize

## 1. Feature Overview

**Purpose**: Fix image size mismatch — AI returns 939x704 instead of the configured 500x1000 for Pinterest. Uses a two-pronged approach:
1. **Pass `aspect_ratio` + `output_megapixels` to OpenRouter** as AI generation hints
2. **Add Pillow-based resize** as a safety net to guarantee exact pixel dimensions

**Business Value**: Pinterest requires portrait-oriented images (ideally 500x1000 or 1000x1500). Currently images come out at arbitrary resolutions.

**Scope**:
- `shared/openrouter_client.py`: Add `output_megapixels` parameter
- `modules/visual_generator.py`: Read new config, pass through, add resize
- `config/platforms.yaml`: Add `width`/`height` back (user already added `aspect_ratio` + `output_megapixels`)
- `pyproject.toml`: Add Pillow dependency
- Tests: Update for all changes

**Success Criteria**:
- Generated Pinterest images are exactly 500x1000 pixels on disk
- API request body includes `image_config.aspect_ratio: "2:3"` and `image_config.output_megapixels: 1.0`
- If AI ignores hints, Pillow resize ensures correct output

## 2. Service Ownership

| Service | File | Change |
|---------|------|--------|
| OpenRouterClient | `shared/openrouter_client.py` | Add `output_megapixels` param to `generate_image()` |
| VisualGenerator | `modules/visual_generator.py` | Read new config, pass to client + add resize |
| Config | `config/platforms.yaml` | Add `width: 500, height: 1000` back to pinterest |
| Dependencies | `pyproject.toml` | Add `Pillow>=10.0.0` |

## 3. Detailed Implementation

### 3.1 Config Change — `config/platforms.yaml`

The Pinterest entry currently has:
```yaml
pinterest:
  aspect_ratio: "2:3"
  output_megapixels: 1.0
```

Add `width` and `height` back for the resize target:
```yaml
pinterest:
  width: 500
  height: 1000
  aspect_ratio: "2:3"
  output_megapixels: 1.0
```

**Why both?**
- `aspect_ratio` + `output_megapixels` → sent to OpenRouter as AI hints for better generation
- `width` + `height` → used for Pillow resize to guarantee exact dimensions

The `instagram` section uses the old format (width/height only) and needs no change.

### 3.2 `shared/openrouter_client.py` — Add `output_megapixels`

**Method**: `generate_image()` (line 187)

**Signature change** — add parameter after `size`:
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

**Body change** — after line 221 (`image_config["size"] = size`), add:
```python
if output_megapixels is not None:
    image_config["output_megapixels"] = output_megapixels
```

**Docstring update** — add to Args section:
```
output_megapixels: Optional float for output resolution, e.g. ``1.0``.
    When provided, included in ``image_config.output_megapixels``.
```

### 3.3 `modules/visual_generator.py` — Multiple changes

#### 3.3.1 Add import (top of file, line 19 area)

```python
import io
from typing import Any  # already imported
```

#### 3.3.2 `__init__()` — No change needed (already stores `self._dimensions`)

#### 3.3.3 `_get_dimensions()` — Already handles width/height (line 177-192, no change needed since config will have width/height back)

No change — this method already reads `width`/`height` from config and returns them. Since we're adding `width: 500, height: 1000` back to the config, this method works as-is.

#### 3.3.4 `_get_aspect_ratio()` — Read `aspect_ratio` from config first

Replace lines 194-212:
```python
def _get_aspect_ratio(self, platform: str) -> str:
    """Get aspect ratio string for a platform.

    Checks for explicit ``aspect_ratio`` key in config first.
    Falls back to deriving from width/height, then hardcoded ASPECT_RATIO_MAP.

    Args:
        platform: Platform name.

    Returns:
        Aspect ratio string like "2:3" or "1:1".
    """
    dims = self._dimensions.get(platform)
    if dims:
        # New format: explicit aspect_ratio key
        if "aspect_ratio" in dims:
            return dims["aspect_ratio"]
        # Old format: derive from width/height
        if dims.get("width") and dims.get("height"):
            from math import gcd
            w, h = dims["width"], dims["height"]
            g = gcd(w, h)
            return f"{w // g}:{h // g}"
    return ASPECT_RATIO_MAP.get(platform, "1:1")
```

#### 3.3.5 New method — `_get_output_megapixels()`

Add after `_get_aspect_ratio()` (after line 212):
```python
def _get_output_megapixels(self, platform: str) -> float | None:
    """Get ``output_megapixels`` for a platform from config.

    Args:
        platform: Platform name (e.g. ``"pinterest"``).

    Returns:
        Float value (e.g. ``1.0``) or ``None`` if not configured.
    """
    dims = self._dimensions.get(platform, {})
    mp = dims.get("output_megapixels")
    if mp is not None and mp > 0:
        return float(mp)
    return None
```

#### 3.3.6 `_generate_and_save()` — Add resize + pass output_megapixels

Replace the method body (lines 214-261) with:

```python
async def _generate_and_save(
    self,
    option: ContentOption,
    dimensions: dict[str, int],
) -> str:
    """Generate an image, resize to exact dimensions, and save to disk.

    Args:
        option: ContentOption with an ``image_prompt``.
        dimensions: Dict with ``width`` and ``height`` for final resize.

    Returns:
        Relative file path (e.g. ``"data/images/batch_xxx_1.png"``).
    """
    aspect_ratio = self._get_aspect_ratio(option.platform)
    output_megapixels = self._get_output_megapixels(option.platform)

    logger.info(
        "Generating image for option id=%d platform=%s aspect_ratio=%s output_megapixels=%s",
        option.id,
        option.platform,
        aspect_ratio,
        output_megapixels,
    )

    # Generate image via OpenRouter
    image_bytes = await self._client.generate_image(
        prompt=option.image_prompt or "",
        model=self._model,
        aspect_ratio=aspect_ratio,
        size=self._image_size,
        output_megapixels=output_megapixels,
    )

    # Resize to exact platform dimensions
    if dimensions["width"] > 0 and dimensions["height"] > 0:
        try:
            from PIL import Image as PILImage
            img = PILImage.open(io.BytesIO(image_bytes))
            img = img.resize(
                (dimensions["width"], dimensions["height"]),
                PILImage.LANCZOS,
            )
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            logger.info(
                "Resized image to %dx%d for platform %s",
                dimensions["width"],
                dimensions["height"],
                option.platform,
            )
        except Exception as exc:
            logger.warning(
                "Failed to resize image for option id=%d, using original: %s",
                option.id,
                exc,
            )

    # Build file path
    filename = f"{option.batch_id}_{option.id}.png"
    filepath = os.path.join(self._images_dir, filename)

    # Write to disk
    try:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
    except OSError as exc:
        logger.error("Failed to write image file %s: %s", filepath, exc)
        raise RuntimeError(f"Failed to write image file {filepath}: {exc}") from exc

    logger.info("Saved image to %s (%d bytes)", filepath, len(image_bytes))
    return filename
```

### 3.4 `pyproject.toml` — Add Pillow dependency

Add `"Pillow>=10.0.0"` to the `dependencies` list:

```toml
dependencies = [
    "asyncpg>=0.29.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.0",
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "jinja2>=3.1.0",
    "apscheduler>=3.10.0",
    "click>=8.0.0",
    "Pillow>=10.0.0",      # Image resizing
]
```

## 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| `output_megapixels` not in config | Not sent to API (default AI behavior) |
| `output_megapixels` is 0 or negative | Treated as None — not sent |
| `aspect_ratio` key present | Used directly for AI call |
| `aspect_ratio` missing but width/height present | Derived via GCD |
| Both missing | Falls back to ASPECT_RATIO_MAP |
| Pillow fails to open image | Log warning, save original bytes |
| Invalid dimensions (0 or negative) | Skip resize, save original |
| Corrupted image bytes from API | Pillow raises → caught → original saved |

## 5. Input/Output Specifications

### OpenRouterClient.generate_image()
```python
output_megapixels: float | None  # if provided, must be > 0
```

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

### Config Format — Pinterest
```yaml
pinterest:
  width: 500              # resize target width
  height: 1000            # resize target height
  aspect_ratio: "2:3"     # AI generation hint
  output_megapixels: 1.0  # AI generation hint (resolution tier)
```

## 6. Edge Cases

- **Config has `aspect_ratio` but no `output_megapixels`**: Pass aspect_ratio to AI, skip output_megapixels, still resize
- **Config has neither new nor old format**: Fall back to hardcoded 1024x1024, no additional AI hints sent
- **Image already correct size after AI**: Pillow resize is a no-op
- **Pinterest config missing `width`/`height` but has aspect_ratio**: `_get_dimensions()` returns 1024x1024 defaults — resize won't match expectations. **Config must have width/height for resize to work correctly.**

## 7. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `Pillow` | `>=10.0.0` | Image resizing after AI generation |

## 8. Files to Modify

| File | Change Type |
|------|-------------|
| `config/platforms.yaml` | Add `width: 500, height: 1000` to pinterest section |
| `shared/openrouter_client.py` | Add `output_megapixels` param to `generate_image()` |
| `modules/visual_generator.py` | Update `_get_aspect_ratio()`, add `_get_output_megapixels()`, add resize in `_generate_and_save()` |
| `pyproject.toml` | Add `Pillow>=10.0.0` to dependencies |
| `tests/test_openrouter_client.py` | Add tests for `output_megapixels` |
| `tests/test_visual_generator.py` | Update `sample_config`, add resize + output_megapixels tests |

## 9. Testing Requirements

### 9.1 `test_openrouter_client.py` — New tests for `TestGenerateImage`
1. **`test_generate_image_with_output_megapixels`**: Pass `output_megapixels=1.0`, verify it appears in `image_config`
2. **`test_generate_image_without_output_megapixels`**: Don't pass it, verify no key in `image_config`

### 9.2 `test_visual_generator.py` — Test updates

**Update `sample_config` fixture** (line 33-43):
```python
@pytest.fixture
def sample_config() -> dict:
    return {
        "visual": {
            "model": "openai/dall-e-3",
            "image_size": "0.5K",
            "dimensions": {
                "pinterest": {
                    "width": 500,
                    "height": 1000,
                    "aspect_ratio": "2:3",
                    "output_megapixels": 1.0,
                },
                "instagram": {"width": 1080, "height": 1080},
            },
        },
    }
```

**Update `TestGetDimensions`**:
- `test_returns_pinterest_dimensions` (line 187): Change assertion to `width=500, height=1000`

**Update `TestGetAspectRatio`**:
- `test_returns_pinterest_ratio` stays `"2:3"`
- Add `test_aspect_ratio_from_config_key`: Config with explicit `aspect_ratio` returns it
- Add `test_aspect_ratio_from_dimensions`: Config without `aspect_ratio` derives from width/height

**Add `TestOutputMegapixels`** (new class):
- `test_returns_pinterest_megapixels`: Pinterest returns `1.0`
- `test_returns_none_when_not_configured`: Unknown platform returns `None`
- `test_returns_none_when_zero`: Config has `output_megapixels: 0` → returns `None`

**Add `TestImageResizing`** (new class):
- `test_resizes_to_platform_dimensions`: Mock `generate_image` returning 100x100 image, verify saved file is 500x1000
- `test_skips_resize_on_zero_dimensions`: Dimensions `0,0` → original bytes preserved
- `test_skips_resize_on_failure`: Mock Pillow to raise → warning logged, original bytes preserved

**Update `TestGenerateAndSave`**:
- `test_passes_correct_parameters` (line 315): Add `output_megapixels=1.0` to the assertion

**Update `TestRun`**:
- `test_uses_platform_dimensions` (line 509): Add `output_megapixels=1.0` to assertion
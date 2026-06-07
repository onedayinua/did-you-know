# visual_generator_image_resize.md

## 1. Feature Overview
**Purpose**: Apply platform-specific image dimensions (width/height) from `config/platforms.yaml` to generated images
**Business Value**: Pinterest requires 400x600 images, Instagram requires 500x500. Currently the dimensions are fetched but never applied — the OpenRouter API only receives an aspect ratio, and the raw output is saved at whatever size the model produces.
**Scope**: Add Pillow-based resizing after image generation, before saving to disk
**Success Criteria**: Generated images are resized to the exact platform dimensions specified in `config/platforms.yaml`

## 2. Service Ownership
**Primary Service**: `modules/visual_generator.py` — `_generate_and_save()` method
**Dependent Services**: None (image dimensions are already fetched in `_get_dimensions()`)
**Interface Changes**: None (no API, message, or DB schema changes)

## 3. Detailed Implementation

### 3.1 Add Pillow dependency
**File**: `pyproject.toml`
**Change**: Add `"Pillow>=10.0.0"` to the `dependencies` list

### 3.2 Add import in `visual_generator.py`
**File**: `modules/visual_generator.py`
**Change**: Add `from PIL import Image` to imports

### 3.3 Modify `_generate_and_save()` — Resize after generation
**File**: `modules/visual_generator.py`
**Method**: `_generate_and_save()` (lines 198-244)

**Current flow**:
1. Generate image bytes via OpenRouter (with aspect ratio only)
2. Build filename and filepath
3. Write raw bytes to disk
4. Return filename

**New flow**:
1. Generate image bytes via OpenRouter (with aspect ratio only)
2. Open bytes with Pillow, resize to exact dimensions
3. Save resized image to disk
4. Return filename

**Exact code change** — after the `image_bytes` are received (line 229), before building the filepath (line 232):

```python
# Resize to exact platform dimensions
if dimensions["width"] > 0 and dimensions["height"] > 0:
    try:
        from PIL import Image as PILImage
        import io
        img = PILImage.open(io.BytesIO(image_bytes))
        img = img.resize(
            (dimensions["width"], dimensions["height"]),
            PILImage.LANCZOS  # High-quality downsampling
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        logger.info(
            "Resized image to %dx%d for platform",
            dimensions["width"],
            dimensions["height"],
        )
    except Exception as exc:
        logger.warning("Failed to resize image, using original: %s", exc)
```

### 3.4 Update `_get_aspect_ratio()` to derive from dimensions
**File**: `modules/visual_generator.py`
**Method**: `_get_aspect_ratio()` (lines 187-196)

**Current**: Uses hardcoded `ASPECT_RATIO_MAP` dict.

**New**: Derive aspect ratio from the actual dimensions in config, falling back to the hardcoded map, then to "1:1":

```python
def _get_aspect_ratio(self, platform: str) -> str:
    """Get aspect ratio string for a platform.

    Derives the ratio from the platform dimensions in config.
    Falls back to the hardcoded ASPECT_RATIO_MAP, then to "1:1".

    Args:
        platform: Platform name.

    Returns:
        Aspect ratio string like "2:3" or "1:1".
    """
    dims = self._dimensions.get(platform)
    if dims and dims.get("width") and dims.get("height"):
        from math import gcd
        w, h = dims["width"], dims["height"]
        g = gcd(w, h)
        return f"{w // g}:{h // g}"
    return ASPECT_RATIO_MAP.get(platform, "1:1")
```

This ensures the aspect ratio sent to OpenRouter matches the actual dimensions in config, so the model generates images closer to the target aspect ratio before the final resize.

## 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| Pillow fails to open image bytes | Log warning, save original bytes unchanged |
| Invalid dimensions (0 or negative) | Skip resize, save original bytes |
| Corrupted image bytes from API | Pillow raises exception → caught by try/except → original bytes saved |
| Memory pressure from large images | Pillow handles streaming; no change needed |
| Missing Pillow library | ImportError at module level → app fails fast on startup |

## 5. Input/Output Specifications

**Input** (already exists):
- `dimensions`: `dict[str, int]` with `"width"` and `"height"` keys, both positive ints
- `image_bytes`: Raw PNG bytes from OpenRouter API

**Output** (unchanged):
- `filename`: String like `"batch_xxx_1.png"`
- File on disk at `data/images/{filename}`

**Internal change**: `image_bytes` is resized before writing to disk.

## 6. Edge Cases

- **Dimensions are 0 or negative**: Skip resize entirely (guard clause)
- **Image is already the correct size**: Pillow resize is a no-op in terms of visual quality, but still processes pixels. Acceptable.
- **Aspect ratio mismatch**: If OpenRouter returns a 1:1 image but we need 2:3, the resize will stretch. This is expected — the aspect ratio sent to OpenRouter should match, and the `_get_aspect_ratio()` change ensures this.
- **Very large images**: Pillow handles this efficiently with LANCZOS resampling.
- **Non-PNG output**: OpenRouter returns PNG per the `image_config`. If it changes, Pillow auto-detects format.

## 7. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `Pillow` | `>=10.0.0` | Image resizing |

**No other new dependencies.** No config changes, no API changes, no DB changes.

## 8. Testing Requirements

### 8.1 Unit Tests — `test_visual_generator.py`

**New test class**: `TestImageResizing`

1. **`test_resizes_to_platform_dimensions`**: Mock `generate_image` to return a known-size image. Call `_generate_and_save` with Pinterest dimensions (400x600). Verify the saved image is exactly 400x600.

2. **`test_skips_resize_on_zero_dimensions`**: Call with `{"width": 0, "height": 0}`. Verify the saved image is the original size (no resize applied).

3. **`test_skips_resize_on_resize_failure`**: Mock Pillow to raise an exception. Verify original bytes are saved and a warning is logged.

4. **`test_aspect_ratio_derived_from_dimensions`**: Test that `_get_aspect_ratio("pinterest")` returns `"2:3"` (from 400x600) and `_get_aspect_ratio("instagram")` returns `"1:1"` (from 500x500).

5. **`test_aspect_ratio_fallback`**: Test that unknown platforms fall back to the hardcoded map, then to "1:1".

### 8.2 Existing Tests
- Update `test_uses_platform_dimensions` (line 492) to verify the resize dimensions are passed correctly
- All existing tests should continue to pass

## 9. Deployment Considerations

### 9.1 Dependency Installation
```bash
pip install Pillow>=10.0.0
```
Or if using the project:
```bash
pip install -e .
```
(After Pillow is added to `pyproject.toml`)

### 9.2 Rollback Strategy
- Revert code changes in `visual_generator.py` and `pyproject.toml`
- No data migration needed (images on disk are already at target size — no harm)
- No DB changes to revert

### 9.3 Monitoring
- No new metrics needed
- Existing `logger.info("Saved image to ...")` will show file sizes
- Add a log line for resize success/failure

### 9.4 Performance Impact
- Resizing adds ~10-50ms per image (negligible for batch processing)
- Memory: Pillow loads the full image into memory; for 1024x1024 PNG this is ~4MB — acceptable
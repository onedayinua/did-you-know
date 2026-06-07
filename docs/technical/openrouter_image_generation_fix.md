# openrouter_image_generation_fix.md

## 1. Feature Overview

**Purpose**: Fix image generation in the content pipeline by migrating from the unsupported OpenRouter `/images/generations` endpoint to the supported Chat Completions endpoint with `modalities: ["image"]`.

**Business Value**: Restores image generation capability — currently all 3 image generation attempts fail with 404 errors, leaving `image_path` as `NULL` in the database for all content options.

**Scope**:
- Rewrite `OpenRouterClient.generate_image()` to use `POST /api/v1/chat/completions` with `modalities: ["image"]`
- Update `VisualGenerator._generate_and_save()` to handle the new response format (base64 data URL instead of fetchable URL)
- Update `VisualGenerator._get_dalle_size()` / dimension logic to use OpenRouter's `image_config.aspect_ratio` instead of DALL-E-specific size strings
- Update `VisualGenerator` config to use an OpenRouter-compatible image model (e.g. `google/gemini-2.0-flash-exp-image-generation` or `openai/dall-e-3` via chat completions)

**Not in scope**:
- Changing the image storage mechanism (still saves to `data/images/`)
- Changing the database schema
- Adding new image generation models beyond what's needed for the fix

**Success Criteria**:
- `python main.py generate` produces images for all 3 content options
- `image_path` is populated in the `content_options` table for each generated image
- Images are saved to `data/images/` and are valid PNG files
- All existing tests pass

## 2. Service Ownership

**Primary Service**: `shared/openrouter_client.py` — the `generate_image()` method must be rewritten.

**Dependent Services**:
- `modules/visual_generator.py` — consumes `generate_image()` output; must handle new response format
- `app/scheduler.py` — orchestrates the pipeline; no changes needed (it calls `visual_generator.run()` which is unchanged)

**Interface Changes**:
- `OpenRouterClient.generate_image()` return type stays `bytes` but the internal implementation changes completely
- `VisualGenerator._get_dalle_size()` is replaced with `_get_aspect_ratio()` returning OpenRouter-compatible aspect ratio strings

## 3. Detailed Implementation

### 3.1 OpenRouterClient.generate_image() — Rewrite

**Current behavior** (broken):
```python
# Calls POST /api/v1/images/generations with OpenAI DALL-E body format
body = {"model": "openai/dall-e-3", "prompt": "...", "size": "1024x1792", "quality": "standard", "n": 1}
data = await self._request_with_retry("POST", "images/generations", json=body)
image_url = data["data"][0]["url"]
# Then fetches the URL to get bytes
```

**New behavior**:
```python
# Calls POST /api/v1/chat/completions with modalities and image_config
body = {
    "model": model,  # e.g. "openai/dall-e-3"
    "messages": [{"role": "user", "content": prompt}],
    "modalities": ["image"],
    "image_config": {"aspect_ratio": aspect_ratio},
}
data = await self._request_with_retry("POST", "chat/completions", json=body)
# Parse images from message.images array (base64 data URLs)
images = data["choices"][0]["message"]["images"]
base64_url = images[0]["image_url"]["url"]  # "data:image/png;base64,iVBOR..."
# Decode base64 to bytes
```

**Method signature change**:
```python
# Before
async def generate_image(self, prompt: str, model: str = "openai/dall-e-3", size: str = "1024x1024", quality: str = "standard") -> bytes:

# After
async def generate_image(self, prompt: str, model: str = "openai/dall-e-3", aspect_ratio: str = "1:1") -> bytes:
```

### 3.2 VisualGenerator — Update dimension handling

**Current**: Uses `DALLE_SIZE_MAP` mapping platform → DALL-E size string (e.g. `"1024x1792"`), passes `size` to `generate_image()`.

**New**: Replace `DALLE_SIZE_MAP` with `ASPECT_RATIO_MAP` mapping platform → OpenRouter aspect ratio string:

```python
ASPECT_RATIO_MAP: dict[str, str] = {
    "pinterest": "2:3",    # portrait — closest to 1000x1500
    "instagram": "1:1",    # square — closest to 1080x1080
}
```

Update `_get_dalle_size()` → `_get_aspect_ratio()`:
```python
def _get_aspect_ratio(self, platform: str) -> str:
    return ASPECT_RATIO_MAP.get(platform, "1:1")
```

Update `_generate_and_save()` to pass `aspect_ratio` instead of `size`:
```python
aspect_ratio = self._get_aspect_ratio(option.platform)
image_bytes = await self._client.generate_image(
    prompt=option.image_prompt or "",
    model=self._model,
    aspect_ratio=aspect_ratio,
)
```

### 3.3 Image bytes extraction from base64

In `OpenRouterClient.generate_image()`, after receiving the response:

```python
images = data["choices"][0]["message"]["images"]
base64_url = images[0]["image_url"]["url"]  # "data:image/png;base64,iVBOR..."

# Parse the base64 data URL
import base64
if base64_url.startswith("data:image/"):
    # Format: data:image/png;base64,<base64_data>
    _, base64_part = base64_url.split(",", 1)
    image_bytes = base64.base64.b64decode(base64_part)
else:
    # Fallback: treat as regular URL and fetch it
    client = await self._ensure_client()
    img_response = await client.get(base64_url)
    img_response.raise_for_status()
    image_bytes = img_response.content

return image_bytes
```

### 3.4 Error handling for new response format

Add specific error messages for:
- Missing `choices` array in response
- Missing `message.images` in choice
- Empty `images` array
- Malformed base64 data URL (invalid format or padding)
- Base64 decode failure

## 4. Error Handling

### Expected Failures

| Failure | Cause | Recovery |
|---------|-------|----------|
| Model doesn't support image output | Wrong model slug | Log error, raise `OpenRouterError` |
| Empty `images` array | Model returned text only | Log error with response content, raise `OpenRouterError` |
| Malformed base64 URL | API response format changed | Log error with URL prefix, raise `OpenRouterError` |
| Base64 decode failure | Corrupted data | Log error, raise `OpenRouterError` |
| 4xx errors (unchanged) | Auth, rate limit, etc. | Existing retry logic applies |
| 5xx errors (unchanged) | Server errors | Existing retry logic applies |

### Error Responses

All errors from `generate_image()` should be `OpenRouterError` with:
- `status_code`: HTTP status code (or `None` for decode errors)
- `response_body`: Truncated response body for debugging

### Logging Requirements

- Log the model and aspect ratio before each request (already done for model)
- Log success with image byte count
- Log failure with specific error type and truncated response

## 5. Input/Output Specifications

### OpenRouterClient.generate_image()

**Input**:
| Parameter | Type | Constraints | Default |
|-----------|------|-------------|---------|
| `prompt` | `str` | Non-empty, stripped | Required |
| `model` | `str` | Must be an image-capable model slug | `"openai/dall-e-3"` |
| `aspect_ratio` | `str` | One of: `"1:1"`, `"2:3"`, `"3:2"`, `"3:4"`, `"4:3"`, `"4:5"`, `"5:4"`, `"9:16"`, `"16:9"`, `"21:9"` | `"1:1"` |

**Output**: `bytes` — raw PNG image bytes.

### VisualGenerator._generate_and_save()

**Input**: Same as before, but `dimensions` dict is no longer needed for the API call (only for logging).

**Output**: Same as before — relative file path string.

## 6. Edge Cases

### 6.1 Model doesn't support image output
- Some models on OpenRouter don't support `modalities: ["image"]`
- The API will return a text-only response (no `images` field)
- **Handling**: Check for `images` field presence; if missing, raise `OpenRouterError` with descriptive message

### 6.2 Model returns text + image
- Some models (like Gemini) return both text and image
- **Handling**: Extract only the `images` array; ignore text content

### 6.3 Multiple images returned
- If `n > 1` is supported in the future
- **Handling**: Use only the first image (`images[0]`)

### 6.4 Base64 data URL format variations
- Could be `data:image/png;base64,...` or `data:image/jpeg;base64,...`
- Could theoretically be a regular HTTPS URL instead
- **Handling**: Check prefix; if `data:image/`, parse base64; otherwise fetch URL

### 6.5 Large base64 payload
- Base64-encoded images can be large (several MB)
- **Handling**: No special handling needed; Python's `base64.b64decode()` handles large strings

### 6.6 Concurrent image generation
- Multiple options processed in sequence (not parallel)
- **Handling**: No race conditions; each option is processed independently

## 7. Dependencies

### External Services
- OpenRouter API (`POST /api/v1/chat/completions`) — already used for text generation
- No new external dependencies

### Internal Services
- `shared/openrouter_client.py` — modified
- `modules/visual_generator.py` — modified

### Libraries/Frameworks
- `base64` (stdlib) — already available, no new dependency
- No new pip packages required

### Configuration
- `config/platforms.yaml` — `visual.model` field should be updated to an OpenRouter-compatible image model (e.g. `"openai/dall-e-3"` still works via chat completions)
- No new config keys needed

## 8. Testing Requirements

### Unit Tests

**OpenRouterClient.generate_image()**:
- Test with mock response containing valid base64 data URL → returns decoded bytes
- Test with mock response containing HTTPS URL → fetches and returns bytes
- Test with mock response missing `choices` → raises `OpenRouterError`
- Test with mock response missing `images` → raises `OpenRouterError`
- Test with empty `images` array → raises `OpenRouterError`
- Test with malformed base64 URL → raises `OpenRouterError`
- Test with invalid aspect ratio → behavior depends on API (should be tested)

**VisualGenerator**:
- Test `_get_aspect_ratio("pinterest")` returns `"2:3"`
- Test `_get_aspect_ratio("instagram")` returns `"1:1"`
- Test `_get_aspect_ratio("unknown")` returns `"1:1"` (default)

### Integration Tests
- Run `python main.py generate` with a real API key → verify images are generated and saved
- Verify `image_path` is populated in the database after generation

### Performance Tests
- No specific performance tests needed (same number of API calls as before)

### Security Tests
- Validate that base64 decoding doesn't allow code injection (stdlib `base64.b64decode` is safe)

## 9. Deployment Considerations

### Migration Scripts
- No database migrations needed

### Rollback Strategy
- Revert changes to `shared/openrouter_client.py` and `modules/visual_generator.py`
- The old code will fail with 404 errors (same as current behavior), so rollback is safe

### Monitoring
- Add log line for successful image generation with byte count
- Existing error logging already captures failures

### Performance Impact
- Same number of HTTP requests (1 per image)
- Slightly larger response payload (base64 data URL vs. fetchable URL)
- No significant performance impact
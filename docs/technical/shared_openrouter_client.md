# OpenRouter API Client

## 1. Feature Overview
**Purpose**: Provide a unified async HTTP client for all OpenRouter API calls (text generation + image generation)
**Business Value**: Single point of integration for AI capabilities, consistent error handling, retry logic
**Scope**: `shared/openrouter_client.py` — async wrapper using httpx, handles text and image generation
**Success Criteria**: Text generation returns structured responses, image generation returns image URLs/bytes, retries on transient failures

## 2. Service Ownership
**Primary Service**: `shared/openrouter_client.py`
**Dependent Services**: Module 2 (theme_associator), Module 3 (content_generator), Module 4 (visual_generator)
**Interface Changes**: New shared utility (no external API)

## 3. Detailed Implementation

### File Location
`shared/openrouter_client.py`

### Client Interface

```python
import httpx
from typing import Optional

class OpenRouterClient:
    """Async client for OpenRouter API (text + image generation)."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, timeout: float = 60.0):
        """
        Args:
            api_key: OpenRouter API key (sk-or-...)
            timeout: Request timeout in seconds
        """
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client."""

    async def close(self) -> None:
        """Close the underlying HTTP client."""

    async def generate_text(
        self,
        prompt: str,
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        response_format: Optional[dict] = None
    ) -> str:
        """
        Generate text using OpenRouter chat completion API.

        Args:
            prompt: The user prompt
            model: Model identifier (e.g., "openai/gpt-4o-mini", "anthropic/claude-3-haiku")
            max_tokens: Maximum tokens in response
            temperature: Randomness (0.0-1.0)
            response_format: Optional JSON mode hint (e.g., {"type": "json_object"})

        Returns:
            Generated text content string

        Raises:
            OpenRouterError: On API errors
            OpenRouterRateLimitError: On 429 responses
        """

    async def generate_image(
        self,
        prompt: str,
        model: str = "openai/dall-e-3",
        size: str = "1024x1024",
        quality: str = "standard"
    ) -> bytes:
        """
        Generate an image using OpenRouter image generation API.

        Args:
            prompt: Image description
            model: Image model identifier
            size: Image dimensions (e.g., "1024x1024", "1024x1792")
            quality: "standard" or "hd"

        Returns:
            Image bytes (PNG format)

        Raises:
            OpenRouterError: On API errors
            OpenRouterRateLimitError: On 429 responses
        """
```

### Error Classes

```python
class OpenRouterError(Exception):
    """Base error for OpenRouter API failures."""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body

class OpenRouterRateLimitError(OpenRouterError):
    """Raised on 429 Too Many Requests."""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s", status_code=429)
```

### Retry Strategy

```
- Max retries: 3
- Retry on: 429 (rate limit), 500, 502, 503, 504, timeout
- Backoff: Exponential with jitter
  - Attempt 1: wait 1s + random(0-1s)
  - Attempt 2: wait 2s + random(0-2s)
  - Attempt 3: wait 4s + random(0-4s)
- Do NOT retry on: 400, 401, 403, 404
```

### Request Format

**Text Generation** (`/chat/completions`):
```json
{
    "model": "openai/gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "prompt text here"}
    ],
    "max_tokens": 1000,
    "temperature": 0.7,
    "response_format": {"type": "json_object"}
}
```

**Image Generation** (`/images/generations`):
```json
{
    "model": "openai/dall-e-3",
    "prompt": "image description here",
    "size": "1024x1024",
    "quality": "standard",
    "n": 1
}
```

### Response Parsing

**Text Response**:
```json
{
    "choices": [
        {
            "message": {
                "content": "generated text here"
            }
        }
    ]
}
```
→ Extract `choices[0].message.content`

**Image Response**:
```json
{
    "data": [
        {
            "url": "https://..."
        }
    ]
}
```
→ Fetch image bytes from URL, return bytes

## 4. Error Handling
**Expected Failures**:
- Network timeout (60s default)
- Rate limiting (429)
- Invalid API key (401)
- Model not available (404)
- Malformed response (missing expected fields)
- Image URL unreachable

**Recovery Strategies**:
- Timeout: Retry with exponential backoff
- Rate limit: Respect `retry-after` header, retry
- Invalid key: Raise immediately (no retry)
- Model not available: Raise immediately with model name in message
- Malformed response: Raise OpenRouterError with raw response body
- Image URL fail: Retry fetch once, then raise

**Logging Requirements**:
- INFO: Request sent (model, token count)
- WARNING: Rate limited, retrying
- ERROR: API error after all retries exhausted
- DEBUG: Full request/response bodies (redact API key)

## 5. Input/Output Specifications
**Input Validation**:
- `prompt`: non-empty string
- `model`: non-empty string, format `provider/model-name`
- `max_tokens`: positive integer
- `temperature`: 0.0-2.0
- `size`: must match pattern `{width}x{height}`

**Output Formats**:
- `generate_text()`: `str` (raw text content)
- `generate_image()`: `bytes` (PNG image data)

## 6. Edge Cases
- Empty response from API (choices array empty)
- Image generation returns multiple images (take first)
- Very long prompts exceeding model context window
- API key rotation during active requests
- Network disconnection mid-stream

## 7. Dependencies
- `httpx` for async HTTP
- `OPENROUTER_API_KEY` environment variable

## 8. Testing Requirements
- **Unit tests**: Mock httpx responses, test retry logic, test error handling
- **Integration tests**: Real API calls with test key (limited)
- **Retry tests**: Verify exponential backoff timing
- **Error tests**: Each error code scenario

## 9. Deployment Considerations
- **Migration**: None
- **Rollback**: N/A
- **Monitoring**: Log API call count, latency, error rate
- **Performance**: Connection pooling via httpx (keep-alive)
- **Cost**: Track token usage per generation

"""Async HTTP client for OpenRouter API (text + image generation).

Provides:
- OpenRouterClient: Lazy-initialized async client for chat completions and image generation
- OpenRouterError: Base exception for API failures
- OpenRouterRateLimitError: Exception for 429 rate limit responses with retry timing
"""

import asyncio
import logging
import random
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _truncate_body(body: str, max_len: int = 500) -> str:
    """Truncate a response body for logging, keeping first and last portion.
    
    Args:
        body: The full response body string.
        max_len: Maximum length before truncation.
    
    Returns:
        Truncated string with \"... [truncated N chars] ...\" in the middle.
    """
    if len(body) <= max_len:
        return body
    half = max_len // 2
    return f"{body[:half]}... [truncated {len(body) - max_len} chars] ...{body[-half:]}"


class OpenRouterError(Exception):
    """Base error for OpenRouter API failures."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class OpenRouterRateLimitError(OpenRouterError):
    """Raised on 429 Too Many Requests."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited. Retry after {retry_after}s",
            status_code=429,
        )


class OpenRouterClient:
    """Async client for OpenRouter API (text + image generation).

    Uses lazy client initialization to avoid creating HTTP connections
    until the first request is made. Supports automatic retry with
    exponential backoff for transient failures (429, 5xx, timeout).

    Usage::

        client = OpenRouterClient(api_key="sk-or-...")
        text = await client.generate_text("Tell me a fun fact")
        image_bytes = await client.generate_image("A cat in space")
        await client.close()
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, timeout: float = 60.0):
        """Initialize the client.

        Args:
            api_key: OpenRouter API key (sk-or-...).
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client on first use."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://did-you-know.app",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client, if it was created."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_text(
        self,
        prompt: str,
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
    ) -> str:
        """Generate text using OpenRouter chat completion API.

        Args:
            prompt: The user prompt (must be a non-empty string).
            model: Model identifier (e.g. ``"openai/gpt-4o-mini"``,
                ``"anthropic/claude-3-haiku"``).
            max_tokens: Maximum tokens in the response.
            temperature: Randomness control (0.0–2.0).
            response_format: Optional JSON mode hint, e.g.
                ``{"type": "json_object"}``.

        Returns:
            The generated text content string.

        Raises:
            OpenRouterError: On API errors or malformed responses.
            OpenRouterRateLimitError: On 429 rate-limit responses.
            ValueError: If prompt is empty.
        """
        self._validate_prompt(prompt)

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is not None:
            body["response_format"] = response_format

        logger.info(
            "Sending chat completion request | model=%s | max_tokens=%s",
            model,
            max_tokens,
        )

        data = await self._request_with_retry("POST", "chat/completions", json=body)

        choices = data.get("choices", [])
        if not choices:
            raise OpenRouterError(
                "Empty choices array in chat completion response",
                status_code=200,
                response_body=str(data),
            )

        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise OpenRouterError(
                "Missing message.content in chat completion response",
                status_code=200,
                response_body=str(data),
            )

        return content

    async def generate_image(
        self,
        prompt: str,
        model: str = "openai/dall-e-3",
        aspect_ratio: str = "1:1",
    ) -> bytes:
        """Generate an image using OpenRouter chat completions API with modalities.

        OpenRouter does not support the OpenAI ``/images/generations`` endpoint.
        Instead, image generation is done via ``/chat/completions`` with
        ``modalities: ["image"]`` and an ``image_config`` block.

        Args:
            prompt: Image description (must be a non-empty string).
            model: Image model identifier.
            aspect_ratio: Aspect ratio string, e.g. ``"1:1"`` or ``"2:3"``.

        Returns:
            Image bytes (typically PNG format).

        Raises:
            OpenRouterError: On API errors, malformed responses, or
                if the image data cannot be decoded.
            OpenRouterRateLimitError: On 429 rate-limit responses.
            ValueError: If prompt is empty.
        """
        self._validate_prompt(prompt)

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image"],
            "image_config": {"aspect_ratio": aspect_ratio},
        }

        logger.info(
            "Sending image generation request | model=%s | aspect_ratio=%s",
            model,
            aspect_ratio,
        )

        data = await self._request_with_retry(
            "POST", "chat/completions", json=body
        )

        choices = data.get("choices", [])
        if not choices:
            raise OpenRouterError(
                "Empty choices array in image generation response",
                status_code=200,
                response_body=str(data),
            )

        message = choices[0].get("message", {})
        images = message.get("images")
        if images is None:
            raise OpenRouterError(
                "Missing images in chat completion response",
                status_code=200,
                response_body=str(data),
            )

        if not images:
            raise OpenRouterError(
                "Empty images array in image generation response",
                status_code=200,
                response_body=str(data),
            )

        image_url = images[0].get("image_url", {}).get("url")
        if not image_url:
            raise OpenRouterError(
                "Missing image_url.url in image generation response",
                status_code=200,
                response_body=str(data),
            )

        # Decode base64 data URL
        import base64

        if image_url.startswith("data:image/"):
            try:
                _, base64_part = image_url.split(",", 1)
                return base64.b64decode(base64_part)
            except (ValueError, base64.binascii.Error) as exc:
                raise OpenRouterError(
                    f"Failed to decode base64 image data: {exc}",
                ) from exc
        else:
            # Fallback: treat as regular URL
            try:
                client = await self._ensure_client()
                img_response = await client.get(image_url)
                img_response.raise_for_status()
                return img_response.content
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                raise OpenRouterError(
                    f"Failed to fetch image from {image_url}: {exc}",
                ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_prompt(prompt: str) -> None:
        """Validate that prompt is a non-empty string."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
    ) -> dict:
        """Send an HTTP request with exponential-backoff retry logic.

        Retries on 429, 5xx, and timeout errors (up to 3 attempts).
        Does **not** retry on 4xx errors other than 429.

        Args:
            method: HTTP method (``"POST"``, ``"GET"``, etc.).
            path: URL path (e.g. ``"/chat/completions"``).
            json: Optional JSON body.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            OpenRouterError: On non-retryable API errors or exhausted retries.
            OpenRouterRateLimitError: On 429 responses.
        """
        max_retries = 3
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                client = await self._ensure_client()
                response = await client.request(method, path, json=json)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(
                    "Request timeout (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                last_exception = exc
                if attempt < max_retries:
                    await self._sleep_with_backoff(attempt)
                continue

            # ---- Non-retryable 4xx errors (except 429) ----
            if response.status_code in (400, 401, 403, 404):
                body_text = response.text
                truncated = _truncate_body(body_text)
                logger.error(
                    "Non-retryable API error | status=%s | body=%s",
                    response.status_code,
                    truncated,
                )
                raise OpenRouterError(
                    f"OpenRouter API error: {response.status_code} - {truncated}",
                    status_code=response.status_code,
                    response_body=body_text,
                )

            # ---- Rate limit (429) ----
            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                logger.warning(
                    "Rate limited (attempt %d/%d) | retry_after=%ss",
                    attempt,
                    max_retries,
                    retry_after,
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_after)
                    continue
                raise OpenRouterRateLimitError(retry_after=retry_after)

            # ---- Server errors (5xx) ----
            if response.status_code >= 500:
                body_text = response.text
                truncated = _truncate_body(body_text)
                logger.warning(
                    "Server error (attempt %d/%d) | status=%s | body=%s",
                    attempt,
                    max_retries,
                    response.status_code,
                    truncated,
                )
                last_exception = OpenRouterError(
                    f"Server error: {response.status_code} - {truncated}",
                    status_code=response.status_code,
                    response_body=body_text,
                )
                if attempt < max_retries:
                    await self._sleep_with_backoff(attempt)
                continue

            # ---- Success ----
            response.raise_for_status()
            return response.json()

        # All retries exhausted
        logger.error("All retries exhausted for %s %s", method, path)
        if isinstance(last_exception, OpenRouterError):
            raise last_exception
        raise OpenRouterError(
            f"Request failed after {max_retries} retries: {last_exception}",
        ) from last_exception

    @staticmethod
    async def _sleep_with_backoff(attempt: int) -> None:
        """Sleep with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (1-indexed).
        """
        base_delay = 2 ** (attempt - 1)  # 1, 2, 4
        jitter = random.uniform(0, base_delay)
        delay = base_delay + jitter
        logger.debug("Retry backoff | attempt=%s | delay=%.2fs", attempt + 1, delay)
        await asyncio.sleep(delay)


def _parse_retry_after(response: httpx.Response) -> int:
    """Extract ``retry-after`` header value from a response.

    Falls back to 60 seconds if the header is missing or unparseable.
    """
    raw = response.headers.get("retry-after")
    if raw is None:
        return 60
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 60

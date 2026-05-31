"""Tests for shared/openrouter_client.py."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
    OpenRouterRateLimitError,
    _parse_retry_after,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def client():
    """Return an OpenRouterClient with a test API key."""
    return OpenRouterClient(api_key="sk-or-test-key", timeout=30.0)


# ------------------------------------------------------------------
# Error classes
# ------------------------------------------------------------------


class TestOpenRouterError:
    """Test the base OpenRouterError exception."""

    def test_basic_exception(self):
        """Test that OpenRouterError stores message, status_code, response_body."""
        exc = OpenRouterError("something bad", status_code=401, response_body="unauthorized")
        assert exc.message == "something bad"
        assert exc.status_code == 401
        assert exc.response_body == "unauthorized"
        assert str(exc) == "something bad"

    def test_exception_without_optional_fields(self):
        """Test that OpenRouterError works with just a message."""
        exc = OpenRouterError("generic error")
        assert exc.message == "generic error"
        assert exc.status_code is None
        assert exc.response_body is None


class TestOpenRouterRateLimitError:
    """Test the rate-limit subclass."""

    def test_default_retry_after(self):
        """Test default retry_after is 60 seconds."""
        exc = OpenRouterRateLimitError()
        assert exc.retry_after == 60
        assert exc.status_code == 429

    def test_custom_retry_after(self):
        """Test custom retry_after value."""
        exc = OpenRouterRateLimitError(retry_after=30)
        assert exc.retry_after == 30

    def test_message_includes_retry_after(self):
        """Test that the error message mentions the retry_after value."""
        exc = OpenRouterRateLimitError(retry_after=45)
        assert "45" in exc.message
        assert "Rate limited" in exc.message


# ------------------------------------------------------------------
# _parse_retry_after helper
# ------------------------------------------------------------------


class TestParseRetryAfter:
    """Test the _parse_retry_after utility."""

    def test_valid_header(self):
        """Test parsing a valid integer retry-after header."""
        response = MagicMock(spec=httpx.Response)
        response.headers = {"retry-after": "30"}
        assert _parse_retry_after(response) == 30

    def test_missing_header(self):
        """Test fallback when retry-after header is missing."""
        response = MagicMock(spec=httpx.Response)
        response.headers = {}
        assert _parse_retry_after(response) == 60

    def test_invalid_header(self):
        """Test fallback when retry-after header is not an integer."""
        response = MagicMock(spec=httpx.Response)
        response.headers = {"retry-after": "foobar"}
        assert _parse_retry_after(response) == 60


# ------------------------------------------------------------------
# generate_text
# ------------------------------------------------------------------


class TestGenerateText:
    """Test generate_text() method."""

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_success(self, mock_httpx_client, client):
        """Test successful chat completion returns the content string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, world!"}}]
        }

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        result = await client.generate_text("Say hello")
        assert result == "Hello, world!"

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_json_mode(self, mock_httpx_client, client):
        """Test generate_text with response_format for JSON mode."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}]
        }

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        result = await client.generate_text(
            "Return JSON",
            response_format={"type": "json_object"},
        )
        assert result == '{"key": "value"}'

        # Verify response_format was included in the request body
        _call_body = mock_instance.request.call_args[1]["json"]
        assert _call_body.get("response_format") == {"type": "json_object"}

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_empty_prompt(self, mock_httpx_client, client):
        """Test that empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            await client.generate_text("")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_whitespace_only_prompt(self, mock_httpx_client, client):
        """Test that whitespace-only prompt raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            await client.generate_text("   \n  ")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_empty_choices(self, mock_httpx_client, client):
        """Test that empty choices array raises OpenRouterError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        with pytest.raises(OpenRouterError, match="Empty choices"):
            await client.generate_text("test")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_401_raises_immediately(self, mock_httpx_client, client):
        """Test that 401 errors raise immediately without retry."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        with pytest.raises(OpenRouterError) as exc_info:
            await client.generate_text("test")

        assert exc_info.value.status_code == 401
        # Only one request should be made (no retry)
        assert mock_instance.request.call_count == 1

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_429_retries_then_succeeds(self, mock_httpx_client, client):
        """Test that 429 triggers retry and eventually succeeds."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"retry-after": "1"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {
            "choices": [{"message": {"content": "success after rate limit"}}]
        }

        mock_instance = AsyncMock()
        mock_instance.request.side_effect = [mock_429, mock_200]
        mock_httpx_client.return_value = mock_instance

        with patch("shared.openrouter_client.asyncio.sleep", AsyncMock()) as mock_sleep:
            result = await client.generate_text("test")
            assert result == "success after rate limit"
            assert mock_instance.request.call_count == 2
            mock_sleep.assert_awaited_once_with(1)

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_5xx_retries_then_succeeds(self, mock_httpx_client, client):
        """Test that 5xx errors trigger retry and eventually succeed."""
        mock_502 = MagicMock()
        mock_502.status_code = 502
        mock_502.text = "bad gateway"

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {
            "choices": [{"message": {"content": "success after 502"}}]
        }

        mock_instance = AsyncMock()
        mock_instance.request.side_effect = [mock_502, mock_200]
        mock_httpx_client.return_value = mock_instance

        with patch("shared.openrouter_client.asyncio.sleep", AsyncMock()) as mock_sleep:
            result = await client.generate_text("test")
            assert result == "success after 502"
            assert mock_instance.request.call_count == 2

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_all_retries_exhausted_on_5xx(self, mock_httpx_client, client):
        """Test that repeated 5xx errors eventually raise after all retries."""
        mock_503 = MagicMock()
        mock_503.status_code = 503
        mock_503.text = "service unavailable"

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_503
        mock_httpx_client.return_value = mock_instance

        with patch("shared.openrouter_client.asyncio.sleep", AsyncMock()):
            with pytest.raises(OpenRouterError) as exc_info:
                await client.generate_text("test")

            assert exc_info.value.status_code == 503
            # 1 original + 2 retries = 3 total (max_retries=3)
            assert mock_instance.request.call_count == 3

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_all_retries_exhausted_on_429(self, mock_httpx_client, client):
        """Test that repeated 429 errors raise OpenRouterRateLimitError."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"retry-after": "5"}

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_429
        mock_httpx_client.return_value = mock_instance

        with patch("shared.openrouter_client.asyncio.sleep", AsyncMock()):
            with pytest.raises(OpenRouterRateLimitError) as exc_info:
                await client.generate_text("test")

            assert exc_info.value.retry_after == 5

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_timeout_retries(self, mock_httpx_client, client):
        """Test that timeout triggers retry and eventually succeeds."""
        mock_instance = AsyncMock()
        mock_instance.request.side_effect = [
            httpx.TimeoutException("timeout"),
            MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "recovered"}}]},
            ),
        ]
        mock_httpx_client.return_value = mock_instance

        with patch("shared.openrouter_client.asyncio.sleep", AsyncMock()):
            result = await client.generate_text("test")
            assert result == "recovered"
            assert mock_instance.request.call_count == 2


# ------------------------------------------------------------------
# generate_image
# ------------------------------------------------------------------


class TestGenerateImage:
    """Test generate_image() method."""

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_success(self, mock_httpx_client, client):
        """Test successful image generation returns image bytes."""
        # Mock the /images/generations response
        mock_gen_response = MagicMock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "data": [{"url": "https://example.com/image.png"}]
        }

        # Mock the image URL fetch response
        mock_img_response = MagicMock()
        mock_img_response.status_code = 200
        mock_img_response.content = b"fake-image-bytes"

        mock_instance = AsyncMock()
        mock_instance.request.side_effect = [mock_gen_response]
        mock_instance.get.return_value = mock_img_response
        mock_httpx_client.return_value = mock_instance

        result = await client.generate_image("A cat")
        assert result == b"fake-image-bytes"
        # Verify the GET was called for the image URL
        mock_instance.get.assert_awaited_once_with("https://example.com/image.png")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_empty_data_array(self, mock_httpx_client, client):
        """Test that empty data array raises OpenRouterError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        with pytest.raises(OpenRouterError, match="Empty data"):
            await client.generate_image("test")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_missing_url(self, mock_httpx_client, client):
        """Test that missing url field raises OpenRouterError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"url": None}]}

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        with pytest.raises(OpenRouterError, match="Missing url"):
            await client.generate_image("test")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_image_url_fetch_failure_retry(self, mock_httpx_client, client):
        """Test that image URL fetch is retried once on failure."""
        # Mock generation response
        mock_gen_response = MagicMock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "data": [{"url": "https://example.com/image.png"}]
        }

        # First GET fails, second succeeds
        mock_img_response_success = MagicMock()
        mock_img_response_success.status_code = 200
        mock_img_response_success.content = b"recovered-image"

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_gen_response
        mock_instance.get.side_effect = [
            httpx.TimeoutException("timeout"),
            mock_img_response_success,
        ]
        mock_httpx_client.return_value = mock_instance

        result = await client.generate_image("test")
        assert result == b"recovered-image"
        assert mock_instance.get.call_count == 2

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_image_url_fetch_exhausted(self, mock_httpx_client, client):
        """Test that image URL fetch raises OpenRouterError after retrying."""
        mock_gen_response = MagicMock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            "data": [{"url": "https://example.com/image.png"}]
        }

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_gen_response
        mock_instance.get.side_effect = httpx.HTTPError("connection failed")
        mock_httpx_client.return_value = mock_instance

        with pytest.raises(OpenRouterError, match="Failed to fetch image"):
            await client.generate_image("test")

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_empty_prompt(self, mock_httpx_client, client):
        """Test that empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            await client.generate_image("")


# ------------------------------------------------------------------
# Retry timing (exponential backoff with jitter)
# ------------------------------------------------------------------


class TestRetryBackoff:
    """Test that exponential backoff with jitter is used."""

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_backoff_timing(self, mock_httpx_client, client):
        """Test that sleep is called with the correct exponential backoff values."""
        mock_503 = MagicMock()
        mock_503.status_code = 503
        mock_503.text = "error"

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_503
        mock_httpx_client.return_value = mock_instance

        with patch("shared.openrouter_client.asyncio.sleep", AsyncMock()) as mock_sleep:
            with patch("shared.openrouter_client.random.uniform") as mock_uniform:
                mock_uniform.side_effect = [0.5, 1.5, 3.0]  # jitter values

                with pytest.raises(OpenRouterError):
                    await client.generate_text("test")

                # After attempt 1: sleep 1 + 0.5 = 1.5
                # After attempt 2: sleep 2 + 1.5 = 3.5
                # After attempt 3: sleep 4 + 3.0 = 7.0 (but we don't sleep after last)
                assert mock_sleep.await_count == 2
                # Check that sleep was called with approximately correct values
                sleep_args = [c[0][0] for c in mock_sleep.await_args_list]
                assert sleep_args[0] == pytest.approx(1.5, rel=0.1)
                assert sleep_args[1] == pytest.approx(3.5, rel=0.1)


# ------------------------------------------------------------------
# Client lifecycle
# ------------------------------------------------------------------


class TestClientLifecycle:
    """Test client initialization and teardown."""

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_lazy_initialization(self, mock_httpx_client, client):
        """Test that the HTTP client is not created until the first request."""
        assert client._client is None
        mock_httpx_client.assert_not_called()

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_close(self, mock_httpx_client, client):
        """Test that close() properly cleans up the client."""
        mock_instance = AsyncMock()
        mock_httpx_client.return_value = mock_instance

        # Trigger lazy init
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_instance.request.return_value = mock_response

        await client.generate_text("hello")
        assert client._client is not None

        await client.close()
        assert client._client is None
        mock_instance.aclose.assert_awaited_once()

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_async_context_manager(self, mock_httpx_client):
        """Test that async context manager works."""
        mock_instance = AsyncMock()
        mock_httpx_client.return_value = mock_instance

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_instance.request.return_value = mock_response

        async with OpenRouterClient(api_key="test") as cm:
            result = await cm.generate_text("hello")
            assert result == "ok"

        mock_instance.aclose.assert_awaited_once()


# ------------------------------------------------------------------
# Client initialization headers
# ------------------------------------------------------------------


class TestClientHeaders:
    """Test that the client is initialized with correct headers."""

    @patch("shared.openrouter_client.httpx.AsyncClient")
    async def test_headers(self, mock_httpx_client, client):
        """Test that the client passes correct headers to httpx."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_httpx_client.return_value = mock_instance

        await client.generate_text("test")

        # Verify AsyncClient was created with correct headers
        _call_kwargs = mock_httpx_client.call_args[1]
        assert _call_kwargs["headers"]["Authorization"] == "Bearer sk-or-test-key"
        assert _call_kwargs["headers"]["Content-Type"] == "application/json"
        assert "HTTP-Referer" in _call_kwargs["headers"]
        assert _call_kwargs["timeout"] == 30.0
        assert _call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
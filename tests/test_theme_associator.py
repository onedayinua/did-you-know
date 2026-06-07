"""Tests for modules/theme_associator.py — ThemeAssociator class.

Covers:
- ``_generate_theme()`` — prompt formatting, retry prompt, API error handling
- ``_clean_theme_name()`` — stripping quotes, truncating to 3 words, empty handling
- ``_is_duplicate()`` — exact match, substring match, no match, case insensitivity
- ``_save_theme()`` — successful insert, error handling
- ``run()`` — full pipeline: success, duplicate retry flow, all retries exhausted
- Edge cases: empty response, too many words, special characters, Unicode
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import timedelta

from modules.theme_associator import ThemeAssociator
from shared.models import Theme, Trend


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def sample_config() -> dict:
    """Full config dict as loaded from content_template.yaml."""
    return {
        "theme_prompt": (
            "Given the trend '{keyword}', find associations: related cooking concepts, "
            "ingredients, cultural angles, or health connections. Based on these "
            "associations, create a short theme name (up to 3 words) that fits "
            "naturally into: 'Did you know that {{theme}}?'\n\n"
            "Return ONLY the theme name, nothing else. Example: \"Crispy Cooking\""
        ),
        "deduplication": {
            "min_hours_between_similar": 12,
        },
        "text_model": "openai/gpt-4o-mini",
    }


@pytest.fixture
def db_pool() -> AsyncMock:
    """Mock asyncpg connection pool with async helpers."""
    pool = AsyncMock()
    pool.fetch = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def openrouter_client() -> AsyncMock:
    """Mock OpenRouterClient with async generate_text."""
    client = AsyncMock()
    client.generate_text = AsyncMock()
    return client


@pytest.fixture
def associator(
    db_pool: AsyncMock,
    openrouter_client: AsyncMock,
    sample_config: dict,
) -> ThemeAssociator:
    """ThemeAssociator instance with mocked db pool, client, and sample config."""
    return ThemeAssociator(db_pool, openrouter_client, sample_config)


@pytest.fixture
def sample_trend() -> Trend:
    """A sample Trend model for testing."""
    return Trend(id=1, keyword="air fryer recipes", score=85.0, source="google_trends")


# ===================================================================
# _generate_theme
# ===================================================================


class TestGenerateTheme:
    """OpenRouter-based theme name generation."""

    async def test_formats_prompt_from_config(self, associator: ThemeAssociator, openrouter_client: AsyncMock):
        """Prompt is formatted with the keyword from config template."""
        openrouter_client.generate_text.return_value = "Crispy Cooking"

        result = await associator._generate_theme("air fryer recipes")

        assert result == "Crispy Cooking"
        openrouter_client.generate_text.assert_awaited_once()
        prompt_arg = openrouter_client.generate_text.call_args[1]["prompt"]
        assert "air fryer recipes" in prompt_arg
        assert "theme name" in prompt_arg

    async def test_retry_prompt_is_different(self, associator: ThemeAssociator, openrouter_client: AsyncMock):
        """Retry prompt asks for a different theme."""
        openrouter_client.generate_text.return_value = "Alternative Theme"

        result = await associator._generate_theme("air fryer recipes", is_retry=True)

        assert result == "Alternative Theme"
        prompt_arg = openrouter_client.generate_text.call_args[1]["prompt"]
        assert "used recently" in prompt_arg
        assert "different one" in prompt_arg

    async def test_passes_correct_model_and_params(self, associator: ThemeAssociator, openrouter_client: AsyncMock):
        """Correct model, max_tokens, and temperature are passed to generate_text."""
        openrouter_client.generate_text.return_value = "Test Theme"

        await associator._generate_theme("test keyword")

        call_kwargs = openrouter_client.generate_text.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-4o-mini"
        assert call_kwargs["max_tokens"] == 50
        assert call_kwargs["temperature"] == 0.7

    async def test_strips_response_whitespace(self, associator: ThemeAssociator, openrouter_client: AsyncMock):
        """Response is stripped of leading/trailing whitespace."""
        openrouter_client.generate_text.return_value = "  Crispy Cooking\n"

        result = await associator._generate_theme("keyword")

        assert result == "Crispy Cooking"

    async def test_raises_on_api_error(self, associator: ThemeAssociator, openrouter_client: AsyncMock):
        """API errors are re-raised after logging."""
        openrouter_client.generate_text.side_effect = RuntimeError("API failure")

        with pytest.raises(RuntimeError, match="API failure"):
            await associator._generate_theme("keyword")


# ===================================================================
# _clean_theme_name
# ===================================================================


class TestCleanThemeName:
    """Theme name cleaning and validation."""

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is removed."""
        assert ThemeAssociator._clean_theme_name("  Crispy Cooking  ") == "Crispy Cooking"

    def test_strips_double_quotes(self):
        """Surrounding double quotes are removed."""
        assert ThemeAssociator._clean_theme_name('"Crispy Cooking"') == "Crispy Cooking"

    def test_strips_single_quotes(self):
        """Surrounding single quotes are removed."""
        assert ThemeAssociator._clean_theme_name("'Crispy Cooking'") == "Crispy Cooking"

    def test_strips_trailing_period(self):
        """Trailing period is removed."""
        assert ThemeAssociator._clean_theme_name("Crispy Cooking.") == "Crispy Cooking"

    def test_strips_trailing_exclamation(self):
        """Trailing exclamation mark is removed."""
        assert ThemeAssociator._clean_theme_name("Crispy Cooking!") == "Crispy Cooking"

    def test_strips_trailing_question_mark(self):
        """Trailing question mark is removed."""
        assert ThemeAssociator._clean_theme_name("Crispy Cooking?") == "Crispy Cooking"

    def test_truncates_to_three_words(self):
        """More than 3 words are truncated to first 3."""
        result = ThemeAssociator._clean_theme_name("Spicy Crispy Chicken Wings")
        assert result == "Spicy Crispy Chicken"

    def test_three_words_unchanged(self):
        """Exactly 3 words are left unchanged."""
        assert ThemeAssociator._clean_theme_name("Crispy Chicken Wings") == "Crispy Chicken Wings"

    def test_one_word_unchanged(self):
        """Single word is left unchanged."""
        assert ThemeAssociator._clean_theme_name("Crispy") == "Crispy"

    def test_two_words_unchanged(self):
        """Two words are left unchanged."""
        assert ThemeAssociator._clean_theme_name("Crispy Cooking") == "Crispy Cooking"

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert ThemeAssociator._clean_theme_name("") == ""

    def test_whitespace_only(self):
        """Whitespace-only string returns empty string."""
        assert ThemeAssociator._clean_theme_name("   ") == ""

    def test_combined_punctuation(self):
        """Multiple punctuation marks are handled."""
        assert ThemeAssociator._clean_theme_name('"Crispy Cooking!?"') == "Crispy Cooking"

    def test_unicode_characters(self):
        """Unicode characters are preserved."""
        result = ThemeAssociator._clean_theme_name("São Paulo Cooking")
        assert result == "São Paulo Cooking"


# ===================================================================
# _is_duplicate
# ===================================================================


class TestIsDuplicate:
    """Deduplication logic against recently used themes."""

    async def test_returns_true_on_exact_match(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """Exact match returns True."""
        db_pool.fetchrow.return_value = {"name": "Crispy Cooking"}

        result = await associator._is_duplicate("Crispy Cooking", 12)

        assert result is True

    async def test_returns_true_on_substring_match(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """Substring match in DB returns True."""
        db_pool.fetchrow.return_value = {"name": "Crispy Cooking"}

        result = await associator._is_duplicate("Cooking", 12)

        assert result is True

    async def test_returns_false_when_no_match(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """No matching theme returns False."""
        db_pool.fetchrow.return_value = None

        result = await associator._is_duplicate("Unique Theme", 12)

        assert result is False

    async def test_case_insensitive_matching(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """ILIKE provides case-insensitive matching."""
        db_pool.fetchrow.return_value = {"name": "crispy cooking"}

        result = await associator._is_duplicate("Crispy Cooking", 12)

        assert result is True

    async def test_passes_correct_hours_interval(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """The hours parameter is passed as timedelta to the query."""
        db_pool.fetchrow.return_value = None

        await associator._is_duplicate("Test Theme", 24)

        db_pool.fetchrow.assert_awaited_once()
        args = db_pool.fetchrow.call_args[0]
        assert isinstance(args[1], timedelta)
        assert args[1].days == 1

    async def test_empty_theme_name(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """Empty theme name returns False (no match possible)."""
        db_pool.fetchrow.return_value = None

        result = await associator._is_duplicate("", 12)

        assert result is False


# ===================================================================
# _save_theme
# ===================================================================


class TestSaveTheme:
    """Database INSERT operations for themes."""

    async def test_inserts_and_returns_theme(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """Inserts a theme and returns a Theme model with generated id."""
        db_pool.fetchrow.return_value = {
            "id": 42,
            "name": "Crispy Cooking",
            "trend_id": 1,
            "created_at": None,
        }

        result = await associator._save_theme("Crispy Cooking", 1)

        assert isinstance(result, Theme)
        assert result.id == 42
        assert result.name == "Crispy Cooking"
        assert result.trend_id == 1

    async def test_raises_when_insert_returns_none(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """Raises RuntimeError if INSERT RETURNING yields no row."""
        db_pool.fetchrow.return_value = None

        with pytest.raises(RuntimeError, match="INSERT into themes table returned no row"):
            await associator._save_theme("fail", 1)

    async def test_correct_query_parameters(self, associator: ThemeAssociator, db_pool: AsyncMock):
        """Verifies the SQL query and parameters passed to the DB."""
        db_pool.fetchrow.return_value = {
            "id": 1,
            "name": "Test Theme",
            "trend_id": 5,
            "created_at": None,
        }

        await associator._save_theme("Test Theme", 5)

        db_pool.fetchrow.assert_called_once()
        args = db_pool.fetchrow.call_args[0]
        assert "INSERT INTO themes" in args[0]
        assert "Test Theme" in args
        assert 5 in args


# ===================================================================
# run() — full pipeline
# ===================================================================


class TestRun:
    """Full pipeline integration tests (mocked)."""

    async def test_full_successful_flow(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_trend: Trend,
    ):
        """Full flow: generate -> dedup (no duplicate) -> save -> return Theme."""
        openrouter_client.generate_text.return_value = "Crispy Cooking"
        db_pool.fetchrow.side_effect = [
            None,  # _is_duplicate returns False (no match)
            {      # _save_theme returns saved record
                "id": 10,
                "name": "Crispy Cooking",
                "trend_id": 1,
                "created_at": None,
            },
        ]

        result = await associator.run(sample_trend)

        assert isinstance(result, Theme)
        assert result.id == 10
        assert result.name == "Crispy Cooking"
        assert result.trend_id == 1

    async def test_duplicate_retries_with_alternative(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_trend: Trend,
    ):
        """When first theme is a duplicate, retries with alternative prompt."""
        openrouter_client.generate_text.side_effect = [
            "Crispy Cooking",     # First attempt — duplicate
            "Healthy Baking",     # Second attempt — not a duplicate
        ]
        db_pool.fetchrow.side_effect = [
            {"name": "Crispy Cooking"},  # _is_duplicate returns True (first attempt)
            None,                         # _is_duplicate returns False (second attempt)
            {                             # _save_theme
                "id": 11,
                "name": "Healthy Baking",
                "trend_id": 1,
                "created_at": None,
            },
        ]

        result = await associator.run(sample_trend)

        assert result.name == "Healthy Baking"
        assert openrouter_client.generate_text.await_count == 2

    async def test_all_retries_exhausted_accepts_duplicate(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_trend: Trend,
    ):
        """After all retries exhausted, last theme is accepted even if duplicate."""
        openrouter_client.generate_text.side_effect = [
            "Crispy Cooking",     # Attempt 1 — duplicate
            "Healthy Baking",     # Attempt 2 — duplicate
            "Spicy Grilling",     # Attempt 3 — duplicate (last attempt)
        ]
        db_pool.fetchrow.side_effect = [
            {"name": "Crispy Cooking"},  # _is_duplicate True
            {"name": "Healthy Baking"},  # _is_duplicate True
            {"name": "Spicy Grilling"},  # _is_duplicate True
            {                            # _save_theme (accepted despite duplicate)
                "id": 12,
                "name": "Spicy Grilling",
                "trend_id": 1,
                "created_at": None,
            },
        ]

        result = await associator.run(sample_trend)

        assert result.name == "Spicy Grilling"
        assert openrouter_client.generate_text.await_count == 3

    async def test_empty_response_retries(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_trend: Trend,
    ):
        """Empty response from AI triggers a retry."""
        openrouter_client.generate_text.side_effect = [
            "",                   # Attempt 1 — empty response
            "Crispy Cooking",     # Attempt 2 — valid response (not duplicate)
        ]
        db_pool.fetchrow.side_effect = [
            None,  # _is_duplicate returns False
            {      # _save_theme
                "id": 13,
                "name": "Crispy Cooking",
                "trend_id": 1,
                "created_at": None,
            },
        ]

        result = await associator.run(sample_trend)

        assert result.name == "Crispy Cooking"
        assert openrouter_client.generate_text.await_count == 2

    async def test_api_error_raises(
        self,
        associator: ThemeAssociator,
        openrouter_client: AsyncMock,
        sample_trend: Trend,
    ):
        """API error during generation raises immediately."""
        openrouter_client.generate_text.side_effect = RuntimeError("API failure")

        with pytest.raises(RuntimeError, match="API failure"):
            await associator.run(sample_trend)

    async def test_cleaned_theme_used_for_save(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_trend: Trend,
    ):
        """Cleaned theme name (truncated, stripped) is saved to DB."""
        openrouter_client.generate_text.return_value = '"Spicy Crispy Chicken Wings Extra"'
        db_pool.fetchrow.side_effect = [
            None,  # _is_duplicate returns False
            {      # _save_theme
                "id": 14,
                "name": "Spicy Crispy Chicken",
                "trend_id": 1,
                "created_at": None,
            },
        ]

        result = await associator.run(sample_trend)

        assert result.name == "Spicy Crispy Chicken"


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Additional edge-case coverage."""

    async def test_config_without_theme_prompt(self, db_pool: AsyncMock, openrouter_client: AsyncMock):
        """Config without theme_prompt key uses empty string default."""
        assoc = ThemeAssociator(db_pool, openrouter_client, {})
        assert assoc._prompt_template == ""

    async def test_config_without_deduplication(self, db_pool: AsyncMock, openrouter_client: AsyncMock):
        """Config without deduplication key uses 12 hours default."""
        assoc = ThemeAssociator(db_pool, openrouter_client, {"theme_prompt": "test"})
        assert assoc._min_hours == 12

    async def test_config_without_min_hours(self, db_pool: AsyncMock, openrouter_client: AsyncMock):
        """Dedup config without min_hours_between_similar uses 12 hours default."""
        assoc = ThemeAssociator(
            db_pool,
            openrouter_client,
            {"theme_prompt": "test", "deduplication": {}},
        )
        assert assoc._min_hours == 12

    async def test_trend_with_unicode_keyword(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
    ):
        """Unicode keyword is handled correctly."""
        trend = Trend(id=2, keyword="recette de cuisine", score=90.0, source="google_trends")
        openrouter_client.generate_text.return_value = "French Cooking"
        db_pool.fetchrow.side_effect = [
            None,
            {
                "id": 20,
                "name": "French Cooking",
                "trend_id": 2,
                "created_at": None,
            },
        ]

        result = await associator.run(trend)

        assert result.name == "French Cooking"

    async def test_special_characters_in_keyword(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
    ):
        """Special characters in keyword are handled."""
        trend = Trend(id=3, keyword="best-ever BBQ ribs!", score=95.0, source="google_trends")
        openrouter_client.generate_text.return_value = "BBQ Master"
        db_pool.fetchrow.side_effect = [
            None,
            {
                "id": 21,
                "name": "BBQ Master",
                "trend_id": 3,
                "created_at": None,
            },
        ]

        result = await associator.run(trend)

        assert result.name == "BBQ Master"

    async def test_duplicate_check_with_special_chars(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
    ):
        """Special characters in theme name for dedup check are passed correctly."""
        db_pool.fetchrow.return_value = None

        await associator._is_duplicate("Crispy & Tasty", 12)

        db_pool.fetchrow.assert_awaited_once()
        args = db_pool.fetchrow.call_args[0]
        assert "Crispy & Tasty" in args

    async def test_save_theme_returns_proper_model(
        self,
        associator: ThemeAssociator,
        db_pool: AsyncMock,
    ):
        """_save_theme returns a Theme model with all fields populated."""
        from datetime import datetime

        now = datetime.now()
        db_pool.fetchrow.return_value = {
            "id": 100,
            "name": "Test Theme",
            "trend_id": 7,
            "created_at": now,
        }

        result = await associator._save_theme("Test Theme", 7)

        assert isinstance(result, Theme)
        assert result.id == 100
        assert result.name == "Test Theme"
        assert result.trend_id == 7
        assert result.created_at == now

    async def test_generate_theme_with_empty_config_prompt(
        self,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
    ):
        """Empty prompt template falls through gracefully."""
        assoc = ThemeAssociator(db_pool, openrouter_client, {"theme_prompt": ""})
        openrouter_client.generate_text.return_value = "Fallback Theme"

        result = await assoc._generate_theme("keyword")

        assert result == "Fallback Theme"
        openrouter_client.generate_text.assert_awaited_once()

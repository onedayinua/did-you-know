"""Tests for modules/text_validator.py — TextValidator class.

Covers:
- ``_parse_scores()`` — JSON parsing and score extraction with clamping
- ``validate()`` — full validation pipeline (disabled, API failure, success)
- ``_save_results()`` — database operations with upsert
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.text_validator import DEFAULT_SCORES, TextValidator


# ===================================================================
# Constants
# ===================================================================

CONTENT_OPTION_ID = 42
FACT = "Air fryers use rapid air technology to create crispy food without oil."
HASHTAGS = ["#AirFryer", "#HealthyCooking", "#CrispyFood"]
IMG_TITLE = "The Secret to Perfect Air Fryer Crispiness"

VALID_JSON_RESPONSE = (
    '{"toxicity_score": 0.95, "politeness_score": 0.90, "grammar_score": 0.85, '
    '"sentiment_score": 0.80, "readability_score": 0.88, "img_title_score": 0.92}'
)

EXPECTED_SCORES = {
    "toxicity_score": 0.95,
    "politeness_score": 0.90,
    "grammar_score": 0.85,
    "sentiment_score": 0.80,
    "readability_score": 0.88,
    "img_title_score": 0.92,
}


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def db_pool() -> AsyncMock:
    """Mock asyncpg connection pool with execute."""
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.execute.return_value = "INSERT 0 1"
    return pool


@pytest.fixture
def openrouter_client() -> AsyncMock:
    """Mock OpenRouterClient with generate_text returning valid JSON."""
    client = AsyncMock()
    client.generate_text = AsyncMock()
    client.generate_text.return_value = VALID_JSON_RESPONSE
    return client


@pytest.fixture
def validation_config() -> dict:
    """Full validation config dict with validation enabled."""
    return {
        "enabled": True,
        "model": "openai/gpt-4o-mini",
        "prompt": "Analyze: {fact} {hashtags} {img_title}",
    }


@pytest.fixture
def disabled_config() -> dict:
    """Validation config dict with validation disabled."""
    return {
        "enabled": False,
    }


@pytest.fixture
def validator(
    db_pool: AsyncMock,
    openrouter_client: AsyncMock,
    validation_config: dict,
) -> TextValidator:
    """TextValidator instance with mocked dependencies and validation enabled."""
    return TextValidator(db_pool, openrouter_client, validation_config)


@pytest.fixture
def disabled_validator(
    db_pool: AsyncMock,
    openrouter_client: AsyncMock,
    disabled_config: dict,
) -> TextValidator:
    """TextValidator instance with mocked dependencies and validation disabled."""
    return TextValidator(db_pool, openrouter_client, disabled_config)


# ===================================================================
# _parse_scores
# ===================================================================


class TestParseScores:
    """JSON parsing and score extraction from LLM responses."""

    def test_valid_json(self, validator: TextValidator):
        """Parses a valid JSON response with all 6 scores and returns correct values."""
        scores = validator._parse_scores(VALID_JSON_RESPONSE)
        assert scores == EXPECTED_SCORES

    def test_partial_json(self, validator: TextValidator):
        """JSON missing some keys defaults those keys to 0.5."""
        partial = '{"toxicity_score": 0.95, "grammar_score": 0.85}'
        scores = validator._parse_scores(partial)
        assert scores["toxicity_score"] == 0.95
        assert scores["grammar_score"] == 0.85
        # Missing keys should default to 0.5
        assert scores["politeness_score"] == 0.5
        assert scores["sentiment_score"] == 0.5
        assert scores["readability_score"] == 0.5
        assert scores["img_title_score"] == 0.5

    def test_out_of_range_values(self, validator: TextValidator):
        """Values > 1.0 or < 0.0 are clamped to [0.0, 1.0]."""
        out_of_range = (
            '{"toxicity_score": 1.5, "politeness_score": -0.5, "grammar_score": 2.0, '
            '"sentiment_score": -1.0, "readability_score": 0.88, "img_title_score": 0.92}'
        )
        scores = validator._parse_scores(out_of_range)
        assert scores["toxicity_score"] == 1.0
        assert scores["politeness_score"] == 0.0
        assert scores["grammar_score"] == 1.0
        assert scores["sentiment_score"] == 0.0
        assert scores["readability_score"] == 0.88
        assert scores["img_title_score"] == 0.92

    def test_invalid_json(self, validator: TextValidator):
        """Non-JSON string returns DEFAULT_SCORES."""
        scores = validator._parse_scores("not valid json at all")
        assert scores == DEFAULT_SCORES

    def test_non_numeric_values(self, validator: TextValidator):
        """Values that are strings or null use defaults for those keys."""
        non_numeric = (
            '{"toxicity_score": "high", "politeness_score": null, "grammar_score": 0.85, '
            '"sentiment_score": "0.80", "readability_score": null, "img_title_score": 0.92}'
        )
        scores = validator._parse_scores(non_numeric)
        # Numeric value should be parsed
        assert scores["grammar_score"] == 0.85
        assert scores["img_title_score"] == 0.92
        # Non-numeric values should default to 0.5
        assert scores["toxicity_score"] == 0.5
        assert scores["politeness_score"] == 0.5
        assert scores["sentiment_score"] == 0.5
        assert scores["readability_score"] == 0.5


# ===================================================================
# validate
# ===================================================================


class TestValidate:
    """Full validation pipeline — disabled, API failure, and success paths."""

    async def test_disabled_validation(
        self,
        disabled_validator: TextValidator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
    ):
        """When enabled=False, saves DEFAULT_SCORES and does not call the API."""
        scores = await disabled_validator.validate(
            content_option_id=CONTENT_OPTION_ID,
            fact=FACT,
            hashtags=HASHTAGS,
            img_title=IMG_TITLE,
        )
        assert scores == DEFAULT_SCORES
        openrouter_client.generate_text.assert_not_called()
        db_pool.execute.assert_called_once()

    async def test_api_failure(
        self,
        validator: TextValidator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
    ):
        """When generate_text raises an Exception, saves DEFAULT_SCORES and logs error."""
        openrouter_client.generate_text.side_effect = Exception("API connection failed")

        with patch("modules.text_validator.logger") as mock_logger:
            scores = await validator.validate(
                content_option_id=CONTENT_OPTION_ID,
                fact=FACT,
                hashtags=HASHTAGS,
                img_title=IMG_TITLE,
            )

        assert scores == DEFAULT_SCORES
        mock_logger.exception.assert_called_once()
        # Should still save to DB
        db_pool.execute.assert_called_once()

    async def test_successful_validation(
        self,
        validator: TextValidator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
    ):
        """When API returns valid JSON, parses scores and saves to DB."""
        scores = await validator.validate(
            content_option_id=CONTENT_OPTION_ID,
            fact=FACT,
            hashtags=HASHTAGS,
            img_title=IMG_TITLE,
        )
        assert scores == EXPECTED_SCORES
        openrouter_client.generate_text.assert_called_once()
        db_pool.execute.assert_called_once()

    async def test_calls_generate_text_with_correct_params(
        self,
        validator: TextValidator,
        openrouter_client: AsyncMock,
    ):
        """Verifies the prompt includes fact, hashtags, and img_title."""
        await validator.validate(
            content_option_id=CONTENT_OPTION_ID,
            fact=FACT,
            hashtags=HASHTAGS,
            img_title=IMG_TITLE,
        )
        call_kwargs = openrouter_client.generate_text.call_args[1]
        prompt = call_kwargs["prompt"]
        assert FACT in prompt
        assert " ".join(HASHTAGS) in prompt
        assert IMG_TITLE in prompt
        assert call_kwargs["model"] == "openai/gpt-4o-mini"
        assert call_kwargs["max_tokens"] == 500
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["response_format"] == {"type": "json_object"}

    async def test_passes_content_option_id_to_db(
        self,
        validator: TextValidator,
        db_pool: AsyncMock,
    ):
        """Verifies the DB execute call includes the content_option_id."""
        await validator.validate(
            content_option_id=CONTENT_OPTION_ID,
            fact=FACT,
            hashtags=HASHTAGS,
            img_title=IMG_TITLE,
        )
        args = db_pool.execute.call_args[0]
        # First argument is the SQL query, second is content_option_id
        assert args[1] == CONTENT_OPTION_ID


# ===================================================================
# _save_results
# ===================================================================


class TestSaveResults:
    """Database upsert operations for validation results."""

    async def test_saves_all_fields(
        self,
        validator: TextValidator,
        db_pool: AsyncMock,
    ):
        """Verifies execute is called with correct SQL and all 13 parameters."""
        await validator._save_results(
            content_option_id=CONTENT_OPTION_ID,
            scores=EXPECTED_SCORES,
            model_used="openai/gpt-4o-mini",
            validation_prompt="Analyze: {fact} {hashtags} {img_title}",
            raw_response=VALID_JSON_RESPONSE,
            fact=FACT,
            hashtags=HASHTAGS,
            img_title=IMG_TITLE,
        )
        db_pool.execute.assert_called_once()
        args = db_pool.execute.call_args[0]

        # Should have 13 parameters (query + 12 values)
        assert len(args) == 14  # query + 13 params

        # Check query is an INSERT statement
        query = args[0]
        assert "INSERT INTO text_validation_results" in query

        # Check positional parameters
        assert args[1] == CONTENT_OPTION_ID
        assert args[2] == EXPECTED_SCORES["toxicity_score"]
        assert args[3] == EXPECTED_SCORES["politeness_score"]
        assert args[4] == EXPECTED_SCORES["grammar_score"]
        assert args[5] == EXPECTED_SCORES["sentiment_score"]
        assert args[6] == EXPECTED_SCORES["readability_score"]
        assert args[7] == EXPECTED_SCORES["img_title_score"]
        assert args[8] == len(FACT)
        assert args[9] == len(HASHTAGS)
        assert args[10] == len(IMG_TITLE)
        assert args[11] == "openai/gpt-4o-mini"
        assert args[12] == "Analyze: {fact} {hashtags} {img_title}"
        assert args[13] == VALID_JSON_RESPONSE

    async def test_handles_db_failure(
        self,
        validator: TextValidator,
        db_pool: AsyncMock,
    ):
        """When execute raises an Exception, logs error but still returns scores."""
        db_pool.execute.side_effect = Exception("Database connection lost")

        with patch("modules.text_validator.logger") as mock_logger:
            result = await validator._save_results(
                content_option_id=CONTENT_OPTION_ID,
                scores=EXPECTED_SCORES,
                model_used="openai/gpt-4o-mini",
                validation_prompt="test prompt",
                raw_response=VALID_JSON_RESPONSE,
                fact=FACT,
                hashtags=HASHTAGS,
                img_title=IMG_TITLE,
            )

        mock_logger.exception.assert_called_once()
        # Should still return the scores even on DB failure
        assert result == EXPECTED_SCORES

    async def test_upsert_behavior(self, validator: TextValidator, db_pool: AsyncMock):
        """Verifies the SQL contains ON CONFLICT for upsert."""
        await validator._save_results(
            content_option_id=CONTENT_OPTION_ID,
            scores=DEFAULT_SCORES,
            model_used="openai/gpt-4o-mini",
            validation_prompt="test",
            raw_response="test",
            fact="test",
            hashtags=["#test"],
            img_title="test",
        )
        query = db_pool.execute.call_args[0][0]
        assert "ON CONFLICT" in query
        assert "DO UPDATE SET" in query
        assert "content_option_id" in query

    async def test_handles_none_hashtags(
        self,
        validator: TextValidator,
        db_pool: AsyncMock,
    ):
        """When hashtags is None, defaults to empty list (hashtag_count=0)."""
        await validator._save_results(
            content_option_id=CONTENT_OPTION_ID,
            scores=DEFAULT_SCORES,
            model_used="openai/gpt-4o-mini",
            validation_prompt="test",
            raw_response="test",
            fact="test fact",
            hashtags=None,
            img_title="test title",
        )
        args = db_pool.execute.call_args[0]
        # hashtag_count is the 9th positional param (index 9)
        assert args[9] == 0
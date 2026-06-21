"""TextValidator module — validates generated text for quality and safety.

Provides the TextValidator class which:
1. Takes generated fact + hashtags + img_title as input
2. Sends a configurable prompt to an LLM for scoring
3. Parses the JSON response into structured scores
4. Saves results to the text_validation_results table

Validation is best-effort and non-blocking:
- If the LLM call fails, default scores (0.5) are used
- If validation is disabled, default scores are saved
- Content is always saved regardless of validation outcome
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SCORES: dict[str, float] = {
    "toxicity_score": 0.5,
    "politeness_score": 0.5,
    "grammar_score": 0.5,
    "sentiment_score": 0.5,
    "readability_score": 0.5,
    "img_title_score": 0.5,
}


class TextValidator:
    """Validates generated text for quality and safety metrics.

    For each content option, sends a configurable prompt to an LLM
    and parses the JSON response into structured scores (0.0–1.0).
    Results are saved to the ``text_validation_results`` table.

    Args:
        db_pool: An asyncpg connection pool (or mock with ``fetchval``/``execute``).
        openrouter_client: An OpenRouterClient instance with ``generate_text()``.
        config: The validation config dict with keys:
            ``enabled`` (bool), ``model`` (str), ``prompt`` (str template).
    """

    def __init__(self, db_pool: Any, openrouter_client: Any, config: dict[str, Any]) -> None:
        self._db = db_pool
        self._client = openrouter_client
        self._enabled: bool = config.get("enabled", True)
        self._model: str = config.get("model", "openai/gpt-4o-mini")
        self._prompt_template: str = config.get(
            "prompt",
            "Analyze the following text for toxicity, politeness, grammar, "
            "sentiment, and readability. Return JSON with scores 0.0–1.0.",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def validate(
        self,
        content_option_id: int,
        fact: str,
        hashtags: list[str],
        img_title: str = "",
    ) -> dict[str, float]:
        """Run validation on a generated text and save results.

        Args:
            content_option_id: The content option ID to associate results with.
            fact: The generated fact text.
            hashtags: The list of hashtags.
            img_title: The image title text overlay.

        Returns:
            Dict with score keys (``toxicity_score``, ``politeness_score``, etc.)
            or ``DEFAULT_SCORES`` if validation is disabled or fails.
        """
        if not self._enabled:
            logger.info("Text validation disabled; skipping for option %d", content_option_id)
            return await self._save_results(
                content_option_id=content_option_id,
                scores=dict(DEFAULT_SCORES),
                model_used=self._model,
                validation_prompt="",
                raw_response="(disabled)",
                fact=fact,
                hashtags=hashtags,
                img_title=img_title,
            )

        hashtags_str = " ".join(hashtags) if hashtags else ""
        prompt = self._prompt_template.format(fact=fact, hashtags=hashtags_str, img_title=img_title)

        logger.info(
            "Running text validation for content_option_id=%d | model=%s",
            content_option_id,
            self._model,
        )

        try:
            response = await self._client.generate_text(
                prompt=prompt,
                model=self._model,
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception:
            logger.exception("Text validation API call failed for option %d", content_option_id)
            return await self._save_results(
                content_option_id=content_option_id,
                scores=dict(DEFAULT_SCORES),
                model_used=self._model,
                validation_prompt=prompt,
                raw_response="(error: API call failed)",
                fact=fact,
                hashtags=hashtags,
                img_title=img_title,
            )

        scores = self._parse_scores(response)
        return await self._save_results(
            content_option_id=content_option_id,
            scores=scores,
            model_used=self._model,
            validation_prompt=prompt,
            raw_response=response,
            fact=fact,
            hashtags=hashtags,
            img_title=img_title,
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_scores(self, response: str) -> dict[str, float]:
        """Parse the JSON response from the LLM into score dict.

        Args:
            response: Raw JSON string from the LLM.

        Returns:
            Dict with score keys, falling back to defaults for missing keys.
            All values are clamped to [0.0, 1.0].
        """
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in validation response; using defaults")
            return dict(DEFAULT_SCORES)

        # Handle both JSON object ({"toxicity_score": 0.95}) and JSON array ([{...}])
        if isinstance(data, list):
            if data:
                data = data[0]
            else:
                data = {}

        if not isinstance(data, dict):
            logger.warning("Unexpected JSON type (%s) in validation response; using defaults", type(data).__name__)
            return dict(DEFAULT_SCORES)

        scores = dict(DEFAULT_SCORES)
        for key in scores:
            val = data.get(key)
            if isinstance(val, (int, float)):
                scores[key] = max(0.0, min(1.0, float(val)))
        return scores

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------

    async def _save_results(
        self,
        content_option_id: int,
        scores: dict[str, float],
        model_used: str,
        validation_prompt: str,
        raw_response: str,
        fact: str = "",
        hashtags: list[str] | None = None,
        img_title: str = "",
    ) -> dict[str, float]:
        """Save validation results to the database.

        Uses INSERT ... ON CONFLICT to upsert by content_option_id,
        so re-running validation updates the existing row.

        Args:
            content_option_id: The content option ID.
            scores: Dict with score keys.
            model_used: The model identifier used for validation.
            validation_prompt: The exact prompt sent to the LLM.
            raw_response: The raw LLM response.
            fact: The original fact text (for length calculation).
            hashtags: The hashtags list (for count calculation).
            img_title: The image title (for length calculation).

        Returns:
            The scores dict that was saved.
        """
        if hashtags is None:
            hashtags = []
        query = """
            INSERT INTO text_validation_results
                (content_option_id, toxicity_score, politeness_score, grammar_score,
                 sentiment_score, readability_score, img_title_score,
                 fact_length, hashtag_count, img_title_length,
                 model_used, validation_prompt, raw_response)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (content_option_id) DO UPDATE SET
                toxicity_score = EXCLUDED.toxicity_score,
                politeness_score = EXCLUDED.politeness_score,
                grammar_score = EXCLUDED.grammar_score,
                sentiment_score = EXCLUDED.sentiment_score,
                readability_score = EXCLUDED.readability_score,
                img_title_score = EXCLUDED.img_title_score,
                fact_length = EXCLUDED.fact_length,
                hashtag_count = EXCLUDED.hashtag_count,
                img_title_length = EXCLUDED.img_title_length,
                model_used = EXCLUDED.model_used,
                validation_prompt = EXCLUDED.validation_prompt,
                raw_response = EXCLUDED.raw_response,
                created_at = CURRENT_TIMESTAMP
        """
        try:
            await self._db.execute(
                query,
                content_option_id,
                scores.get("toxicity_score"),
                scores.get("politeness_score"),
                scores.get("grammar_score"),
                scores.get("sentiment_score"),
                scores.get("readability_score"),
                scores.get("img_title_score"),
                len(fact),
                len(hashtags),
                len(img_title),
                model_used,
                validation_prompt,
                raw_response,
            )
        except Exception:
            logger.exception("Failed to save validation results for option %d", content_option_id)

        return scores
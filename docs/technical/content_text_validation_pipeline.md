# content_text_validation_pipeline.md

## 1. Feature Overview
**Purpose**: Add a configurable text validation pipeline that runs after text generation to score generated content for toxicity, politeness, grammar quality, and other metrics. Results are stored in the database and displayed on the preview page.

**Business Value**: Ensures generated content is safe, polite, and high-quality before being posted to social media platforms. Provides editors with data-driven quality signals to make approval decisions.

**Scope**:
- New `TextValidator` module that runs configurable validation checks on generated text (fact + hashtags + img_title)
- New database table `text_validation_results` to store per-option validation scores
- Configurable validation prompt (editable like `text_prompt` in `content_template.yaml`)
- Configurable validation model (separate from `text_model`)
- Display validation results (toxicity score, politeness score, grammar score, etc.) on the preview page
- Validation runs automatically after text generation AND can be re-run manually

**Success Criteria**:
- Validation scores are stored in the database for each content option
- Preview page shows a "Content Quality" metrics section with scores
- Editor can re-run validation with a different model
- Validation prompt is editable via `content_template.yaml`
- Validation model is configurable separately from the generation model
- `img_title` is included in the validation prompt and scored alongside fact and hashtags

## 2. Service Ownership
**Primary Service**: `content-generator` (Module 3) — new `TextValidator` class
**Dependent Services**: 
- `app/routes.py` — new API endpoint for re-running validation
- `app/templates/preview/base.html` — display validation results
- `shared/models.py` — new `TextValidationResult` Pydantic model

**Interface Changes**:
- Database: New table `text_validation_results`
- Config: New section `validation` in `content_template.yaml`
- API: New endpoint `POST /options/{id}/validate-text`
- Template: New metrics section in preview page

## 3. Detailed Implementation

### 3.1 Database Changes
New migration `0006_create_text_validation_results.sql`:
```sql
CREATE TABLE IF NOT EXISTS text_validation_results (
    id SERIAL PRIMARY KEY,
    content_option_id INTEGER NOT NULL REFERENCES content_options(id) ON DELETE CASCADE,
    toxicity_score FLOAT,
    politeness_score FLOAT,
    grammar_score FLOAT,
    sentiment_score FLOAT,
    readability_score FLOAT,
    img_title_score FLOAT,
    fact_length INTEGER,
    hashtag_count INTEGER,
    img_title_length INTEGER,
    model_used VARCHAR(100) NOT NULL,
    validation_prompt TEXT,
    raw_response TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_text_validation_content_option_id ON text_validation_results(content_option_id);
CREATE INDEX idx_text_validation_created_at ON text_validation_results(created_at DESC);
```

### 3.2 Config Changes (`config/content_template.yaml`)
Add a new `validation` section:
```yaml
# Text validation settings — runs after text generation to score quality
validation:
  enabled: true
  model: "openai/gpt-4o-mini"
  prompt: >
    You are a content quality analyzer. Analyze the following text and return
    a JSON object with scores from 0.0 to 1.0 (1.0 = best) for each metric:

    - toxicity_score: How non-toxic is this text? (1.0 = completely safe/clean)
    - politeness_score: How polite and respectful is this text?
    - grammar_score: How grammatically correct is this text?
    - sentiment_score: How positive is the sentiment?
    - readability_score: How easy is this text to read?
    - img_title_score: How appropriate and on-brand is the image title? (1.0 = perfect)

    Text to analyze:
    Fact: "{fact}"
    Hashtags: {hashtags}
    Image Title: "{img_title}"

    Return ONLY valid JSON: {{"toxicity_score": 0.95, "politeness_score": 0.90, "grammar_score": 0.85, "sentiment_score": 0.80, "readability_score": 0.88, "img_title_score": 0.90}}
```

### 3.3 New Module: `modules/text_validator.py`
Create a new `TextValidator` class:

```python
"""TextValidator module — validates generated text for quality and safety.

Provides the TextValidator class which:
1. Takes generated fact + hashtags as input
2. Sends a configurable prompt to an LLM for scoring
3. Parses the JSON response into structured scores
4. Saves results to the text_validation_results table
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_SCORES = {
    "toxicity_score": 0.5,
    "politeness_score": 0.5,
    "grammar_score": 0.5,
    "sentiment_score": 0.5,
    "readability_score": 0.5,
    "img_title_score": 0.5,
}


class TextValidator:
    """Validates generated text for quality and safety metrics.

    Args:
        db_pool: An asyncpg connection pool.
        openrouter_client: An OpenRouterClient instance.
        config: The validation config dict with keys:
            ``enabled``, ``model``, ``prompt``.
    """

    def __init__(self, db_pool: Any, openrouter_client: Any, config: dict[str, Any]) -> None:
        self._db = db_pool
        self._client = openrouter_client
        self._enabled: bool = config.get("enabled", True)
        self._model: str = config.get("model", "openai/gpt-4o-mini")
        self._prompt_template: str = config.get(
            "prompt",
            "Analyze the following text for toxicity, politeness, grammar, sentiment, and readability..."
        )

    async def validate(
        self,
        content_option_id: int,
        fact: str,
        hashtags: list[str],
        img_title: str = "",
    ) -> dict[str, float]:
        """Run validation on a generated text and save results.

        Args:
            content_option_id: The content option ID.
            fact: The generated fact text.
            hashtags: The list of hashtags.
            img_title: The image title text overlay.

        Returns:
            Dict with score keys (toxicity_score, politeness_score, etc.)
            or DEFAULT_SCORES if validation is disabled or fails.
        """
        if not self._enabled:
            logger.info("Text validation disabled; skipping")
            return await self._save_results(
                content_option_id=content_option_id,
                scores=DEFAULT_SCORES,
                model_used=self._model,
                validation_prompt="",
                raw_response="(disabled)",
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
                scores=DEFAULT_SCORES,
                model_used=self._model,
                validation_prompt=prompt,
                raw_response=f"(error: API call failed)",
            )

        scores = self._parse_scores(response)
        return await self._save_results(
            content_option_id=content_option_id,
            scores=scores,
            model_used=self._model,
            validation_prompt=prompt,
            raw_response=response,
        )

    def _parse_scores(self, response: str) -> dict[str, float]:
        """Parse the JSON response from the LLM into score dict.

        Args:
            response: Raw JSON string from the LLM.

        Returns:
            Dict with score keys, falling back to defaults for missing keys.
        """
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in validation response; using defaults")
            return dict(DEFAULT_SCORES)

        scores = dict(DEFAULT_SCORES)
        for key in scores:
            val = data.get(key)
            if isinstance(val, (int, float)):
                scores[key] = max(0.0, min(1.0, float(val)))
        return scores

    async def _save_results(
        self,
        content_option_id: int,
        scores: dict[str, float],
        model_used: str,
        validation_prompt: str,
        raw_response: str,
        fact_length: int = 0,
        hashtag_count: int = 0,
        img_title_length: int = 0,
    ) -> dict[str, float]:
        """Save validation results to the database.

        Uses INSERT ... ON CONFLICT to upsert by content_option_id.
        """
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
        # Note: We need a unique constraint on content_option_id for ON CONFLICT.
        # If not added, use a two-step: DELETE then INSERT.
        await self._db.execute(
            query,
            content_option_id,
            scores.get("toxicity_score"),
            scores.get("politeness_score"),
            scores.get("grammar_score"),
            scores.get("sentiment_score"),
            scores.get("readability_score"),
            scores.get("img_title_score"),
            fact_length,
            hashtag_count,
            img_title_length,
            model_used,
            validation_prompt,
            raw_response,
        )
        return scores
```

### 3.4 Integration into ContentGenerator
In `modules/content_generator.py`, modify the `run()` method to call `TextValidator.validate()` after saving each option:

```python
# After saving options in _save_options, call validation
from modules.text_validator import TextValidator

# In __init__, store validation config
self._validation_config: dict[str, Any] = config.get("validation", {})

# In run(), after saving each platform's options:
if self._validation_config.get("enabled", True):
    validator = TextValidator(self._db, self._client, self._validation_config)
    for option in saved:
        await validator.validate(
            content_option_id=option.id,
            fact=option.fact,
            hashtags=option.hashtags,
            img_title=option.img_title or "",
        )
```

### 3.5 New API Endpoint: `POST /options/{id}/validate-text`
In `app/routes.py`, add:

```python
@router.post("/options/{id}/validate-text")
async def validate_option_text(id: int):
    """Re-run text validation for a content option.

    Args:
        id: Content option ID.

    Returns:
        JSON with validation scores.

    Raises:
        HTTPException 404: If option not found.
        HTTPException 500: If validation fails.
    """
    row = await fetch_one(
        "SELECT id, fact, hashtags, img_title FROM content_options WHERE id = $1",
        id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content option not found")

    from shared.db import get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import load_config
    from modules.text_validator import TextValidator

    pool = await get_pool()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = OpenRouterClient(api_key)
    config = load_config("content_template")
    validation_config = config.get("validation", {})

    validator = TextValidator(pool, client, validation_config)
    hashtags_raw = row.get("hashtags", [])
    if isinstance(hashtags_raw, str):
        import json
        hashtags = json.loads(hashtags_raw)
    else:
        hashtags = list(hashtags_raw) if hashtags_raw else []

    scores = await validator.validate(
        content_option_id=id,
        fact=row["fact"],
        hashtags=hashtags,
        img_title=row.get("img_title", "") or "",
    )
    await client.close()

    return {"status": "ok", "scores": scores}
```

### 3.6 Template Changes (preview/base.html)
Add a "Content Quality" metrics section to the preview page, below the existing metrics:

```html
{% if validation_results %}
<div class="metrics">
    <h3>Content Quality</h3>
    <div class="metric-row">
        <span class="label">Safety Score</span>
        <span class="value {% if validation_results.toxicity_score >= 0.8 %}under{% elif validation_results.toxicity_score < 0.5 %}over{% endif %}">
            {{ "%.0f"|format(validation_results.toxicity_score * 100) }}%
        </span>
    </div>
    <div class="metric-row">
        <span class="label">Politeness</span>
        <span class="value {% if validation_results.politeness_score >= 0.8 %}under{% elif validation_results.politeness_score < 0.5 %}over{% endif %}">
            {{ "%.0f"|format(validation_results.politeness_score * 100) }}%
        </span>
    </div>
    <div class="metric-row">
        <span class="label">Grammar</span>
        <span class="value {% if validation_results.grammar_score >= 0.8 %}under{% elif validation_results.grammar_score < 0.5 %}over{% endif %}">
            {{ "%.0f"|format(validation_results.grammar_score * 100) }}%
        </span>
    </div>
    <div class="metric-row">
        <span class="label">Sentiment</span>
        <span class="value {% if validation_results.sentiment_score >= 0.6 %}under{% elif validation_results.sentiment_score < 0.3 %}over{% endif %}">
            {{ "%.0f"|format(validation_results.sentiment_score * 100) }}%
        </span>
    </div>
    <div class="metric-row">
        <span class="label">Readability</span>
        <span class="value {% if validation_results.readability_score >= 0.8 %}under{% elif validation_results.readability_score < 0.5 %}over{% endif %}">
            {{ "%.0f"|format(validation_results.readability_score * 100) }}%
        </span>
    </div>
    <div class="metric-row">
        <span class="label">Image Title Quality</span>
        <span class="value {% if validation_results.img_title_score >= 0.8 %}under{% elif validation_results.img_title_score < 0.5 %}over{% endif %}">
            {{ "%.0f"|format(validation_results.img_title_score * 100) }}%
        </span>
    </div>
    <div class="metric-row" style="margin-top:8px;padding-top:8px;border-top:1px solid #eee;">
        <span class="label">Model</span>
        <span class="value" style="font-size:0.75rem;color:#888;">{{ validation_results.model_used }}</span>
    </div>
    <form action="/options/{{ option.id }}/validate-text" method="post" style="margin-top:8px;">
        <button type="submit" class="btn btn-outline" style="font-size:0.75rem;">Re-run Validation</button>
    </form>
</div>
{% endif %}
```

### 3.7 Update Preview Route to Include Validation Results
In `app/routes.py`, modify `preview_all` and `preview_platform` to fetch validation results:

```python
# After fetching the option row:
validation_row = await fetch_one(
    "SELECT toxicity_score, politeness_score, grammar_score, "
    "sentiment_score, readability_score, img_title_score, model_used "
    "FROM text_validation_results "
    "WHERE content_option_id = $1",
    id,
)
validation_results = None
if validation_row:
    validation_results = {
        "toxicity_score": float(validation_row["toxicity_score"]) if validation_row["toxicity_score"] else 0.5,
        "politeness_score": float(validation_row["politeness_score"]) if validation_row["politeness_score"] else 0.5,
        "grammar_score": float(validation_row["grammar_score"]) if validation_row["grammar_score"] else 0.5,
        "sentiment_score": float(validation_row["sentiment_score"]) if validation_row["sentiment_score"] else 0.5,
        "readability_score": float(validation_row["readability_score"]) if validation_row["readability_score"] else 0.5,
        "img_title_score": float(validation_row["img_title_score"]) if validation_row["img_title_score"] else 0.5,
        "model_used": validation_row.get("model_used", ""),
    }

# Pass to template:
return templates.TemplateResponse(
    request,
    f"preview/{platform}.html",
    {
        "option": option,
        "config": config,
        "validation_results": validation_results,
    },
)
```

## 4. Error Handling
**Expected Failures**:
- LLM returns invalid/non-JSON response → fall back to `DEFAULT_SCORES`
- LLM API call fails (timeout, rate limit) → fall back to `DEFAULT_SCORES`, log error
- Database insert fails → log error, scores still returned to caller
- Content option not found on re-validate → 404 HTTP error
- Missing validation config → use hardcoded defaults

**Recovery Strategies**:
- All validation failures use `DEFAULT_SCORES` (0.5 for all metrics) so the pipeline never blocks
- Validation is best-effort — if it fails, content is still generated and saved
- Re-run validation endpoint allows manual retry

**Error Responses**:
```json
// Validation API error
{"detail": "Content option not found"}

// Validation API success
{"status": "ok", "scores": {"toxicity_score": 0.95, ...}}
```

**Logging Requirements**:
- Log at INFO level when validation starts/completes for each option
- Log at WARNING level when JSON parsing fails
- Log at ERROR level when API call fails

## 5. Input/Output Specifications

### Validation Config (`content_template.yaml`)
```yaml
validation:
  enabled: true              # bool, optional, default: true
  model: "openai/gpt-4o-mini"  # string, any OpenRouter model
  prompt: "..."              # string, editable validation prompt with {fact}, {hashtags}, and {img_title} placeholders
```

### API: `POST /options/{id}/validate-text`
- **Request**: No body required
- **Response 200**:
```json
{
  "status": "ok",
  "scores": {
    "toxicity_score": 0.95,
    "politeness_score": 0.90,
    "grammar_score": 0.85,
    "sentiment_score": 0.80,
    "readability_score": 0.88,
    "img_title_score": 0.92
  }
}
```
- **Response 404**: `{"detail": "Content option not found"}`
- **Response 500**: `{"detail": "Validation failed: <error message>"}`

### Database Schema
```sql
CREATE TABLE text_validation_results (
    id SERIAL PRIMARY KEY,
    content_option_id INTEGER NOT NULL REFERENCES content_options(id) ON DELETE CASCADE,
    toxicity_score FLOAT,
    politeness_score FLOAT,
    grammar_score FLOAT,
    sentiment_score FLOAT,
    readability_score FLOAT,
    img_title_score FLOAT,
    fact_length INTEGER,
    hashtag_count INTEGER,
    img_title_length INTEGER,
    model_used VARCHAR(100) NOT NULL,
    validation_prompt TEXT,
    raw_response TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Data Types**:
- All score fields: `FLOAT` (0.0–1.0 range, nullable for graceful degradation)
- `model_used`: `VARCHAR(100)` — OpenRouter model identifier
- `validation_prompt`: `TEXT` — the exact prompt sent to the LLM (for debugging)
- `raw_response`: `TEXT` — the raw LLM response (for debugging)

## 6. Edge Cases
- **Validation disabled** (`enabled: false`): Skip validation entirely, no API call, save default scores
- **Empty fact string**: Still send to LLM with empty fact, LLM should handle gracefully
- **Empty hashtags list**: Format as empty string in prompt
- **Empty or missing img_title**: Pass empty string to prompt; LLM should handle gracefully
- **LLM returns partial scores** (e.g., only toxicity_score): Missing keys default to 0.5
- **LLM returns out-of-range scores** (e.g., 2.5 or -1.0): Clamp to [0.0, 1.0]
- **Concurrent validation requests**: Each content_option_id has its own row; upsert handles conflicts
- **Content option deleted**: Foreign key `ON DELETE CASCADE` cleans up validation results
- **Re-running validation**: Upserts the existing row with new scores and new model info

## 7. Dependencies
- **External Services**: OpenRouter API (same as text generation)
- **Internal Services**: 
  - `shared/db.py` — database pool
  - `shared/openrouter_client.py` — LLM client
  - `shared/config_loader.py` — config loading
- **New Dependencies**: None (uses existing OpenRouter client)
- **Configuration**: 
  - `OPENROUTER_API_KEY` environment variable (already exists)
  - `content_template.yaml` → `validation` section (new)

## 8. Testing Requirements

### Unit Tests (`tests/test_text_validator.py`)
- Test `_parse_scores` with valid JSON response
- Test `_parse_scores` with partial JSON (missing keys)
- Test `_parse_scores` with out-of-range values (clamping)
- Test `_parse_scores` with invalid JSON (falls back to defaults)
- Test `validate` with validation disabled
- Test `validate` with API failure (falls back to defaults)
- Test `validate` with successful API call and DB save

### Integration Tests
- Test full pipeline: generate → validate → display on preview
- Test re-run validation endpoint
- Test that validation results appear on preview page
- Test that deleted content option cascades to delete validation results

### Performance Tests
- Validation adds ~1 API call per content option (typically 1-3 per generation)
- Each call is fast (low max_tokens=500, simple prompt)
- No significant performance impact expected

## 9. Deployment Considerations
- **Migration**: Run `0006_create_text_validation_results.sql` before deploying new code
- **Rollback**: 
  1. Revert code changes
  2. Run `DROP TABLE IF EXISTS text_validation_results CASCADE;` (only if rolling back completely)
- **Monitoring**: 
  - Add log aggregation for validation failures
  - Track average validation scores per platform over time
- **Performance Impact**: Minimal — each validation call is ~200ms with gpt-4o-mini
- **Backward Compatibility**: 
  - Old content options without validation results show no metrics section
  - Preview page gracefully handles missing `validation_results`
  - Old `content_template.yaml` without `validation` section uses hardcoded defaults

## 10. Tasks

1. **Create migration**: `migrations/0006_create_text_validation_results.sql`
2. **Create module**: `modules/text_validator.py` with `TextValidator` class
3. **Update config**: Add `validation` section to `config/content_template.yaml`
4. **Update ContentGenerator**: Integrate `TextValidator` into `run()` method
5. **Add API endpoint**: `POST /options/{id}/validate-text` in `app/routes.py`
6. **Update preview route**: Fetch and pass `validation_results` to template
7. **Update preview template**: Add Content Quality metrics section to `preview/base.html`
8. **Add re-run button**: Add "Re-run Validation" button in preview page
9. **Write unit tests**: `tests/test_text_validator.py`
10. **Write integration tests**: Update `tests/test_routes.py` for new endpoint

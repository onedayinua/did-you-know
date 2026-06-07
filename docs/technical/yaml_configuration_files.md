# YAML Configuration Files

## 1. Feature Overview
**Purpose**: Define all YAML configuration files that drive content generation, platform settings, and queue management
**Business Value**: Externalized configuration allows tuning without code changes
**Scope**: 3 YAML files in `config/` directory: `content_template.yaml`, `platforms.yaml`, `backup_trends.yaml`
**Success Criteria**: All configs loadable by `shared/config_loader.py`, all env var references valid

## 2. Service Ownership
**Primary Service**: `config/` (static configuration)
**Dependent Services**: All modules reference these configs via `config_loader.py`
**Interface Changes**: New configuration files

## 3. Detailed Implementation

### File: `config/content_template.yaml`

```yaml
# Content generation prompts and settings

# Theme prompt — Module 2 uses this to create theme from trend
theme_prompt: >
  Given the trend '{keyword}', find associations: related cooking concepts,
  ingredients, cultural angles, or health connections. Based on these
  associations, create a short theme name (up to 3 words) that fits
  naturally into: 'Did you know that {theme}?'

  Return ONLY the theme name, nothing else. Example: "Crispy Cooking"

# Text prompt — Module 3 uses this to generate fact + hashtags
text_prompt: >
  You are a culinary content creator. The theme is '{theme}'.
  This theme will be used as the topic in: "Did you know that {theme}?"

  Generate a supporting fact and hashtags. Requirements:
  - Fact: engaging, educational, fun tone, 1-2 sentences that expand on the theme
  - Hashtags: relevant to the theme

  Return as JSON: {{"fact": "...", "hashtags": ["...", "..."]}}

# Image prompt — Module 3 uses this to generate image description from fact
image_prompt: >
  You are an image prompt designer. Given this culinary fact:
  "{fact}"

  Create a detailed image description for a Pinterest pin. Style requirements:
  - Warm, appetizing food photography style
  - Bright natural lighting, shallow depth of field
  - Overhead or 45-degree angle
  - Include relevant food ingredients or dish
  - No text overlay (text added separately)


# Platform-specific content limits
platforms:
  pinterest:
    character_limit: 500
    hashtag_count: 5-10
  instagram:
    character_limit: 2200
    hashtag_count: 10-30

# Number of content variations to generate per theme
variations: 3

# Deduplication settings for themes
deduplication:
  min_hours_between_similar: 12
```

### File: `config/platforms.yaml`

```yaml
# Platform configuration for posting

platforms:
  pinterest:
    enabled: true
    api_base: "https://api.pinterest.com/v5"
    board_id: "${PINTEREST_BOARD_ID}"
    access_token: "${PINTEREST_ACCESS_TOKEN}"
  instagram:
    enabled: false
    api_base: "https://graph.instagram.com"
    access_token: "${INSTAGRAM_ACCESS_TOKEN}"

# Visual generation settings
visual:
  model: "dall-e-3"
  style: "food photography, bright, appetizing, clean background"
  dimensions:
    pinterest:
      width: 1000
      height: 1500
    instagram:
      width: 1080
      height: 1080

# Scheduling settings
scheduling:
  post_immediately: true
  cross_post_delay_minutes: 0
```

### File: `config/backup_trends.yaml`

```yaml
# Fallback trends and queue configuration

# Fallback trends used when Google Trends API fails
backup_trends:
  - keyword: "easy dinner recipes"
    score: 85.0
  - keyword: "healthy snacks"
    score: 80.0
  - keyword: "meal prep ideas"
    score: 75.0
  - keyword: "comfort food"
    score: 70.0
  - keyword: "quick breakfast"
    score: 65.0

# Queue management settings
queue:
  max_pending: 10
  expire_days: 7
  cleanup_on_generate: true

# Trend selection settings
trend_history_days: 30
```

## 4. Error Handling
**Expected Failures**:
- YAML syntax error
- Missing required keys
- Invalid env var references

**Recovery Strategies**:
- Syntax error: Fail fast at startup with clear message
- Missing keys: Fail fast at first access with key path
- Invalid env vars: Log warning, leave `${VAR}` as-is

## 5. Input/Output Specifications
**Validation Rules**:
- `variations`: positive integer
- `max_pending`: positive integer
- `expire_days`: positive integer
- `character_limit`: positive integer
- `hashtag_count`: format `min-max` or single integer
- Platform `enabled`: boolean

## 6. Edge Cases
- Empty backup_trends list (Module 1 must handle)
- `hashtag_count` as single number vs range
- Env var returns empty string
- Config file encoding (must be UTF-8)

## 7. Dependencies
- `pyyaml` for loading
- `shared/config_loader.py` for access
- Environment variables: `PINTEREST_BOARD_ID`, `PINTEREST_ACCESS_TOKEN`, `INSTAGRAM_ACCESS_TOKEN`

## 8. Testing Requirements
- **Validation tests**: Load each file, verify all expected keys exist
- **Env var tests**: Verify substitution works with real env vars
- **Schema tests**: Validate types match expected (int vs str)

## 9. Deployment Considerations
- **Migration**: Copy config files to production
- **Rollback**: Revert YAML files
- **Monitoring**: N/A
- **Performance**: Loaded once at startup, cached

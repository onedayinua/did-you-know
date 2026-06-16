# AI Content Channel - Architecture

## Overview
AI-driven social media channel featuring "Did you know?" style culinary entertainment content. The system automates content creation from trend discovery to scheduled posting across multiple platforms.

## Core Principles
1. **Platform Agnostic**: Content creation independent of posting destination
2. **Multiple Options**: Generate several options, human selects best
3. **Template Driven**: Content requirements defined in YAML templates
4. **Human in the Loop**: User selects final post from options
5. **Modular**: Each module is independently testable

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Language | Python 3.11+ | Async-first, type hints |
| AI API | OpenRouter | Text generation (GPT-4o-mini, Claude) + image generation (DALL-E, Stable Diffusion) |
| Trend Source | `pytrends` | Google Trends unofficial API |
| Database | PostgreSQL | Persistent storage for trends, categories, content, posts |
| Migrations | Raw SQL files in `migrations/` | Sequential naming: `0001_name.sql`, tracked via `schema_migrations` table |
| Web Framework | FastAPI | Async REST API + auto-generated OpenAPI docs |
| ASGI Server | Uvicorn | Production-ready async server for FastAPI |
| Templates | Jinja2 | HTML rendering for dashboard UI |
| Scheduler | APScheduler | In-process job scheduling (replaces system cron) |
| Config | YAML files | Content templates, platform settings, queue config |
| HTTP Client | `httpx` | Async HTTP calls to OpenRouter and platform APIs |
| Project Manager | `uv` | Fast Python package manager and virtualenv |

## Pipeline Flow

```
APScheduler (every 2 hours)
    ↓
[1] Trend Selector → saves trend to DB
    ↓
[2] Theme Associator → creates theme (deduplicated via DB)
    ↓
[3] Content Generator → generates text + image prompt, saves to DB (skips if queue full)
    ↓
[4] Visual Generator → creates image from prompt, saves to DB
    ↓
=== Queue holds complete options (text + image) until user approves ===
    ↓
User opens Web UI → sees pending options with images → clicks "Approve"
    ↓
[5] Content Selector → marks selected option in DB, triggers posting
    ↓
[6] Platform Poster → posts to platforms, updates DB with result
```

## Project Structure

```
did-you-know/
├── config/
│   ├── content_template.yaml    # Content generation template (text + image prompts)
│   ├── platforms.yaml           # Platform settings
│   └── backup_trends.yaml       # Fallback trends + queue settings
├── migrations/
│   ├── 0001_create_trends.sql
│   ├── 0002_create_themes.sql
│   ├── 0003_create_content.sql
│   └── 0004_create_posts.sql
├── modules/
│   ├── trend_selector.py        # Module 1
│   ├── theme_associator.py      # Module 2
│   ├── content_generator.py     # Module 3
│   ├── visual_generator.py      # Module 4
│   └── platform_poster.py       # Module 6
├── app/
│   ├── main.py                  # FastAPI app + lifespan (mounts APScheduler)
│   ├── routes.py                # API endpoints (approve, history, dashboard)
│   ├── scheduler.py             # APScheduler job definitions + configuration
│   └── templates/
│       ├── dashboard.html       # Jinja2 single-page UI for content approval
│       └── preview/
│           ├── base.html        # Shared preview layout
│           ├── pinterest.html   # Pinterest pin preview template
│           └── instagram.html   # Instagram post preview template
├── shared/
│   ├── openrouter_client.py     # OpenRouter API wrapper (async via httpx)
│   ├── config_loader.py         # YAML config loading
│   ├── db.py                    # PostgreSQL connection pool (async via asyncpg)
│   ├── migrate.py               # Migration runner
│   └── models.py                # Shared data classes (Pydantic models)
├── main.py                      # CLI entrypoint (generate, serve commands)
├── pyproject.toml               # Dependencies and project metadata
└── .env                         # API keys + DB URL (gitignored)
```

## Data Model

### Entities

**trends** — Stores used trends to avoid repetition.
- Fields: keyword, score, source, timestamp
- Used by: Module 1 (writes), Module 2 (reads)

**themes** — Stores theme usage for deduplication.
- Fields: name (up to 3 words), trend keyword, timestamp
- Used by: Module 2 (writes), Module 3 (reads for dedup)

**content_options** — Stores generated content options with images until user approves.
- Fields: batch ID, theme, fact, hashtags, image prompt, image path, status, timestamp
- Status flow: `pending` → `approved` → `posted` / `expired` / `cancelled`
- Used by: Module 3 (writes text), Module 4 (writes image path), Module 5 (reads + updates status)

**posts** — Tracks published posts and their status.
- Fields: content option ID (FK), platform, image path, status, post URL, error, timestamps
- Status flow: `pending` → `success` / `failed`
- Used by: Module 5 (creates on approve), Module 6 (updates with result)

### Relationships

```
trends 1──* themes 1──* content_options 1──* posts
```

One trend produces one theme. One theme produces multiple content options. Each approved content option produces one post per platform.

## Queue Management

To prevent unbounded growth of pending options (text + image):

```yaml
# config/backup_trends.yaml
queue:
  max_pending: 10           # Skip generation if >= 10 pending options
  expire_days: 7            # Auto-expire options older than 7 days
  cleanup_on_generate: true # Run cleanup before each generation
```

**Behavior**:
1. Before generating, check `SELECT COUNT(*) FROM content_options WHERE status = 'pending'`
2. If count >= `max_pending`, skip generation entirely (log and exit)
3. On each generation, expire old options: `UPDATE content_options SET status = 'expired' WHERE status = 'pending' AND created_at < NOW() - INTERVAL '7 days'`

## Modules

### Module 1: Trend Selector
**Purpose**: Identify trending topics for content creation
**Input**: Google Trends API (via `pytrends`)
**Output**: Exactly one selected trend (saved to `trends` table)
**Trigger**: APScheduler job (every 2 hours, runs async in-process)

**Process**:
1. Fetch fresh trends from Google Trends via `pytrends`
2. Query DB for recently used trends, skip duplicates
3. Select best unused trend
4. Save selected trend to `trends` table

**Fallback Strategies** (in order):
1. Highest-scoring unused trend
2. Highest-scoring trend (even if recently used)

**Configuration** (`config/backup_trends.yaml`):
```yaml
trend_history_days: 30
```

---

### Module 2: Theme Associator
**Purpose**: Create a short, memorable theme name from the trend by finding associations. This theme phrase fills the blank in: *"Did you know that {theme}?"*
**Input**: Selected trend (from `trends` table)
**Output**: Theme name — up to 3 words (saved to `themes` table)

**Tech**: OpenRouter API (text generation model)

**What is an association?**
Given a trend (e.g., "air fryer recipes"), find related concepts that could inspire content — cooking methods, ingredients, cultural connections, health angles, etc. Then distill that into a short theme name that fits naturally into: *"Did you know that ___?"*

**Process**:
1. Load theme prompt template from `config/content_template.yaml`
2. Send trend to OpenRouter with configured prompt
3. Query `themes` table for recently used themes
4. If theme is too similar to a recent one, ask OpenRouter for an alternative
5. Save theme to `themes` table

**Configuration** (`config/content_template.yaml`):
```yaml
theme_prompt: >
  Given the trend '{keyword}', find associations: related cooking concepts,
  ingredients, cultural angles, or health connections. Based on these
  associations, create a short theme name (up to 3 words) that fits
  naturally into: 'Did you know that {theme}?'

deduplication:
  min_hours_between_similar: 12
```

**Output Example**:
```json
{
  "trend": "air fryer recipes",
  "theme": "Crispy Cooking"
}
```

---

### Module 3: Content Generator
**Purpose**: Create multiple content options from theme — first text, then image prompt
**Input**: Theme dict (from Module 2)
**Output**: List of content options with text + image prompt (saved to `content_options` table)
**Queue Check**: Skips generation if pending options >= `max_pending`

**Tech**: OpenRouter API (text generation model) + YAML config

**Process**:
1. Check queue size — if >= `max_pending`, log and exit
2. Expire old pending options (older than `expire_days`)
3. Load text prompt template and image style template from `config/content_template.yaml`
4. **Step 1 — Generate text**: Send theme to OpenRouter using text prompt template → get N variations of (topic, fact, hashtags)
5. **Step 2 — Generate image prompt for each**: Send each text variation to OpenRouter using image style template → get styled image description
6. Parse response into structured content options (text + image prompt)
7. Save all options to `content_options` table with `status = 'pending'`

**Configuration** (`config/content_template.yaml`):
```yaml
text_prompt: >
  You are a culinary content creator. The theme is '{theme}'.
  This theme will be used as the topic in: "Did you know that {theme}?"

  Generate a supporting fact and hashtags. Requirements:
  - Fact: engaging, educational, fun tone, 1-2 sentences that expand on the theme
  - Hashtags: relevant to the theme

  Return as JSON: {{"fact": "...", "hashtags": ["...", "..."]}}

image_prompt: >
  You are an image prompt designer. Given this culinary fact:
  "{fact}"

  Create a detailed image description for a Pinterest pin. Style requirements:
  - Warm, appetizing food photography style
  - Bright natural lighting, shallow depth of field
  - Overhead or 45-degree angle
  - Include relevant food ingredients or dish
  - No text overlay (text added separately)


platforms:
  pinterest:
    character_limit: 500
    hashtag_count: 5-10
  instagram:
    character_limit: 2200
    hashtag_count: 10-30

variations: 2
```

---

### Module 5: Web UI (Content Selector)
**Purpose**: User reviews and approves complete content options (text + image)
**Input**: Complete options from `content_options` table (with generated images)
**Output**: Status changes, triggers posting pipeline

**Tech**: FastAPI + Jinja2 templates + Uvicorn

**Endpoints**:
```
GET  /                                  → Dashboard (all pending options with images)
GET  /options/{id}                      → Single option detail view
POST /options/{id}/approve              → Approve option, trigger posting (Module 6)
POST /options/{id}/cancel               → Cancel option (status → 'cancelled')
POST /options/{id}/regenerate-text      → Regenerate fact + hashtags (keep theme + image)
POST /options/{id}/regenerate-image     → Regenerate image only (keep text), triggers Module 4
POST /options/{id}/mark-posted          → Mark approved option as posted (creates posts record, sets content_options.status = 'posted')
GET  /preview/{id}                      → Preview single post across all platforms
GET  /preview/{id}/{platform}           → Preview single post for specific platform
GET  /history                           → List posted content history
GET  /health                            → Health check
```

**Dashboard UI** (`GET /`):
- Grid of pending option cards showing: theme, fact preview, hashtags, **image thumbnail**, created date
- Each card has action buttons:
  - **View** → opens single option detail
  - **Approve** → triggers Module 6 (posting)
  - **Cancel** → marks as cancelled, removes from queue

**Single Option View** (`GET /options/{id}`):
- Full content details: theme, fact, hashtags, **generated image**
- Action buttons:
  - **Approve** → triggers Module 6 (posting)
  - **Regenerate Text** → calls Module 3 with same theme, replaces fact + hashtags, keeps image
  - **Regenerate Image** → calls Module 4 with same text, generates new image
  - **Cancel** → marks as cancelled
- Preview section showing how post looks on each platform

**Preview Page** (`GET /preview/{id}` and `GET /preview/{id}/{platform}`):
- For approved Pinterest content, two additional buttons are shown:
  - **Post to Pinterest** → fetches image as base64 client-side, calls `sendPinToExtension()` to trigger Chrome extension for manual pin creation
  - **Mark as Posted** → calls `POST /options/{id}/mark-posted` to record the post in the `posts` table directly
- Buttons are only rendered when `option.status == 'approved'` and the platform is `pinterest`

**Preview Templates** (`GET /preview/{id}`):
- Renders content using platform-specific Jinja2 templates
- Shows character count, hashtag count vs platform limits
- Available previews:
  - Pinterest pin layout (square image + description)
  - Instagram post layout (square image + caption)
  - Extensible for future platforms

**Platform Preview Templates** (`templates/preview/`):
```
templates/preview/
  pinterest.html    → Pin-style preview (image + title + description)
  instagram.html    → Post-style preview (image + caption + hashtags)
  base.html         → Shared layout
```

**Action Flow**:
```
Approve:
  → API marks option as 'approved'
  → Calls platform_poster(option_id) [Module 6]
  → Updates post status
  → Returns result to UI

Regenerate Text:
  → API calls Module 3 text generation with same theme
  → Replaces fact + hashtags in content_options
  → Keeps existing image unchanged
  → Returns updated option to UI

Regenerate Image:
  → API calls Module 4 visual generation with existing image prompt
  → Replaces image in content_options
  → Keeps text unchanged
  → Returns updated option to UI

Cancel:
  → API marks option as 'cancelled'
  → Removed from pending queue

Mark as Posted:
  → API creates posts record with status='success'
  → Updates content_options.status to 'posted'
  → Returns post_id to UI, page reloads

Post to Pinterest:
  → Client-side: fetches image as base64
  → Client-side: calls sendPinToExtension() to trigger Chrome extension
  → User completes pin in Pinterest tab manually
  → User clicks "Mark as Posted" to record the post
```

**Run**: `uvicorn app.main:app --reload` (dev) or `python main.py serve` (prod)

---

### Module 4: Visual Generator
**Purpose**: Create images for all content options automatically after text generation
**Input**: Content options with image prompts (from `content_options` table)
**Output**: Generated images saved to `data/images/`, path saved in `content_options` table
**Trigger**: Runs automatically after Module 3 completes

**Tech**: OpenRouter API (image generation: DALL-E, Stable Diffusion, etc.)

**Process**:
1. Module 3 completes text generation
2. Load all new content options from `content_options` table
3. For each option, use the image prompt to call OpenRouter image generation
4. Save images to `data/images/` directory
5. Update `content_options` with image file path

**Configuration** (`config/platforms.yaml`):
```yaml
visual:
  model: "dall-e-3"
  style: "food photography, bright, appetizing, clean background"
  dimensions:
    pinterest: [1000, 1500]
    instagram: [1080, 1080]
```

---

### Module 6: Platform Poster
**Purpose**: Post approved content with image to configured platforms
**Input**: Approved content option (from `content_options` table, triggered by Module 5)
**Output**: Updated post status + URL (in `posts` table)

**Tech**: `httpx` (async HTTP client) for platform REST APIs

**Process**:
1. Load post entry from `posts` table
2. Load platform config from `config/platforms.yaml`
3. Format content for target platform (tags, handles, limits)
4. Upload image and create post via platform API
5. Update `posts` table with status (`success`/`failed`) and post URL
6. Update `content_options` status to `posted`

**Configuration** (`config/platforms.yaml`):
```yaml
platforms:
  pinterest:
    enabled: true
    api_base: "https://api.pinterest.com/v5"
    board_id: "${PINTEREST_BOARD_ID}"
  instagram:
    enabled: false
    api_base: "https://graph.instagram.com"

scheduling:
  post_immediately: true
  cross_post_delay_minutes: 0
```

## Shared Modules

### db.py
**Purpose**: PostgreSQL async connection pool and query helpers
**Used by**: All modules
**Pattern**: Single connection pool via `asyncpg`, async query execution

### openrouter_client.py
**Purpose**: Single async wrapper for all OpenRouter API calls
**Used by**: Modules 2, 3, 4
**Methods**: `generate_text(prompt, model)`, `generate_image(prompt, model)`

### models.py
**Purpose**: Shared Pydantic models for validation and serialization
**Models**: `Trend`, `Theme`, `ContentOption`, `Post`

## APScheduler Configuration

APScheduler runs in-process alongside FastAPI, managed via lifespan events.

- Scheduler type: `AsyncIOScheduler` (async-compatible)
- Generation job: runs every 2 hours
- `max_instances=1` prevents overlapping runs
- `misfire_grace_time=300` (5 min grace period if delayed)
- Scheduler starts on FastAPI startup, shuts down on FastAPI shutdown

**Run**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

## Running the System

```bash
# 1. Run database migrations
python -m shared.migrate

# 2. Start FastAPI server (serves web UI + runs APScheduler)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or via CLI entrypoint:
python main.py serve

# Manual generation (outside scheduler):
python main.py generate
```

The FastAPI server handles both the web dashboard (http://localhost:8000) and the scheduled content generation pipeline (APScheduler runs in-process). No separate cron setup needed.

## Environment Variables (.env)
```
DATABASE_URL=postgresql://user:pass@localhost:5432/did_you_know
OPENROUTER_API_KEY=sk-or-...
PINTEREST_ACCESS_TOKEN=...
PINTEREST_EXTENSION_ID=... (optional, for Chrome extension posting)
INSTAGRAM_ACCESS_TOKEN=...
```

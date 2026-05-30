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

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| AI API | OpenRouter (text generation + image generation) |
| Trend Source | `pytrends` (Google Trends unofficial API) |
| Database | PostgreSQL (persistent storage) |
| Migrations | Raw SQL files in `migrations/` (sequential: `0001_name.sql`) |
| Web UI | Flask (simple single-page app) |
| Config | YAML files |
| Platform APIs | Platform-specific SDKs (e.g., `requests` for REST APIs) |
| Scheduler | System cron (triggers automated pipeline) |
| Project Manager | `uv` (fast Python package manager) |

## Pipeline Flow

```
Cron (every 2 hours)
    ↓
[1] Trend Selector → saves trend to DB
    ↓
[2] Theme Associator → creates theme + category (deduplicated via DB)
    ↓
[3] Content Generator → generates options, saves to DB (skips if queue full)
    ↓
=== Queue holds options until user approves ===
    ↓
User opens Web UI → sees pending options → clicks "Approve"
    ↓
[4] Content Selector → marks selected option in DB
    ↓
[5] Visual Generator → creates image, saves to DB
    ↓
[6] Scheduler → posts to platforms, updates DB with result
```

## Project Structure

```
did-you-know/
├── config/
│   ├── categories.yaml          # Theme categories
│   ├── content_template.yaml    # Content generation template
│   ├── platforms.yaml           # Platform settings
│   └── backup_trends.yaml       # Fallback trends + queue settings
├── migrations/
│   ├── 0001_create_trends.sql
│   ├── 0002_create_categories.sql
│   ├── 0003_create_content.sql
│   └── 0004_create_posts.sql
├── modules/
│   ├── trend_selector.py        # Module 1
│   ├── theme_associator.py      # Module 2
│   ├── content_generator.py     # Module 3
│   ├── visual_generator.py      # Module 5
│   └── scheduler.py             # Module 6
├── web/
│   ├── app.py                   # Flask web server + API routes
│   └── templates/
│       └── dashboard.html       # Single-page UI for content approval
├── shared/
│   ├── openrouter_client.py     # OpenRouter API wrapper
│   ├── config_loader.py         # YAML config loading
│   ├── db.py                    # PostgreSQL connection + queries
│   ├── migrate.py               # Migration runner
│   └── models.py                # Shared data classes
├── main.py                      # CLI orchestrator (generate command)
├── pyproject.toml               # Dependencies and project metadata
└── .env                         # API keys + DB URL (gitignored)
```

## Database Schema

### trends
Tracks used trends to avoid repetition.

```sql
CREATE TABLE trends (
    id SERIAL PRIMARY KEY,
    keyword TEXT NOT NULL,
    score INTEGER,
    source TEXT NOT NULL DEFAULT 'google',
    used_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trends_used_at ON trends (used_at);
CREATE INDEX idx_trends_keyword ON trends (keyword);
```

### categories
Tracks category usage for deduplication.

```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    trend_keyword TEXT NOT NULL,
    used_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_categories_used_at ON categories (used_at);
CREATE INDEX idx_categories_name ON categories (name);
```

### content_options
Stores generated content options until user approves one.

```sql
CREATE TABLE content_options (
    id SERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL,
    trend_keyword TEXT NOT NULL,
    theme TEXT NOT NULL,
    category TEXT NOT NULL,
    topic TEXT NOT NULL,
    fact TEXT NOT NULL,
    hashtags TEXT[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_content_options_status ON content_options (status);
CREATE INDEX idx_content_options_created_at ON content_options (created_at);
```

**Status values**: `pending` → `approved` → `posted` / `expired`

### posts
Tracks published posts and their status.

```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    content_option_id INTEGER NOT NULL REFERENCES content_options(id),
    platform TEXT NOT NULL,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    post_url TEXT,
    error TEXT,
    posted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_posts_content_option_id ON posts (content_option_id);
CREATE INDEX idx_posts_status ON posts (status);
```

## Queue Management

To prevent unbounded growth of pending options:

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
**Purpose**: Identify suitable food-related trends for content creation
**Input**: Google Trends API (via `pytrends`)
**Output**: Exactly one selected trend (saved to `trends` table)
**Trigger**: Cron (every 2 hours via `python main.py generate`)

**Process**:
1. Fetch fresh trends from Google Trends via `pytrends`
2. Filter non-food trends using configurable keyword list
3. Query DB for recently used trends, skip duplicates
4. Select best unused food trend
5. Save selected trend to `trends` table

**Fallback Strategies** (in order):
1. Highest-scoring unused food trend
2. Highest-scoring food trend (even if recently used)
3. Highest-scoring trend from any category
4. Pre-defined backup trends from `config/backup_trends.yaml`

**Configuration** (`config/backup_trends.yaml`):
```yaml
food_keywords:
  - recipe
  - cooking
  - food
  - kitchen
  - ingredient
  - meal
  - bake
  - fry
  - grill

backup_trends:
  - "sourdough bread"
  - "air fryer recipes"
  - "meal prep ideas"

trend_history_days: 30
```

---

### Module 2: Theme Associator
**Purpose**: Assign a category and create a theme from the trend
**Input**: Selected trend (from `trends` table)
**Output**: Theme with category (saved to `categories` table)

**Tech**: OpenRouter API (text generation model for categorization + theme naming)

**Process**:
1. Send trend to OpenRouter, ask: "Which category fits best? [list]"
2. Query `categories` table for recently used categories
3. If category used recently, ask OpenRouter to pick next best
4. Ask OpenRouter: "Create a short theme name for this trend in this category"
5. Save category usage to `categories` table

**Configuration** (`config/categories.yaml`):
```yaml
categories:
  - cooking_techniques
  - kitchen_tools
  - ingredients
  - recipes
  - food_science
  - cultural_foods

deduplication:
  min_hours_between_category: 12
```

**Output Example**:
```json
{
  "trend": "air fryer recipes",
  "theme": "Air Fryer Cooking",
  "category": "cooking_techniques"
}
```

---

### Module 3: Content Generator
**Purpose**: Create multiple content options from theme using templates
**Input**: Theme dict (from Module 2)
**Output**: List of content options (saved to `content_options` table)
**Queue Check**: Skips generation if pending options >= `max_pending`

**Tech**: OpenRouter API (text generation model) + YAML template

**Process**:
1. Check queue size — if >= `max_pending`, log and exit
2. Expire old pending options (older than `expire_days`)
3. Load template from `config/content_template.yaml`
4. Build prompt: theme + template requirements → ask OpenRouter for N variations
5. Parse response into structured content options
6. Save all options to `content_options` table with `status = 'pending'`

**Configuration** (`config/content_template.yaml`):
```yaml
requirements:
  topic_length: "≤3 words"
  fact_style: "Did you know?"
  tone: "engaging, educational, fun"

platforms:
  pinterest:
    character_limit: 500
    hashtag_count: 5-10
  instagram:
    character_limit: 2200
    hashtag_count: 10-30

variations: 3
```

---

### Module 4: Web UI (Content Selector)
**Purpose**: User views pending options and approves one
**Input**: Pending options from `content_options` table
**Output**: Marks approved option as `status = 'approved'`, triggers pipeline

**Tech**: Flask web server + simple HTML/JS frontend

**Endpoints**:
```
GET  /                  → Dashboard (shows pending options)
POST /api/approve/:id  → Approve option, trigger visual generation + posting
GET  /api/history      → Show posted content history
```

**Dashboard UI**:
- Shows all pending options as cards (topic + fact + hashtags)
- Each card has an "Approve" button
- Clicking "Approve" → POST /api/approve/:id → triggers Modules 5→6 automatically
- Shows queue status (e.g., "8 pending, 3 posted today")

**Auto-trigger flow** (on approve):
```
User clicks "Approve"
    → API marks option as 'approved'
    → Calls visual_generator(option_id)
    → Creates post entry in DB
    → Calls scheduler(post_id)
    → Updates post status
    → Returns result to UI
```

**Run**: `python -m web.app` (or `flask run`)

---

### Module 5: Visual Generator
**Purpose**: Create an image for the approved content
**Input**: Approved content option (from DB)
**Output**: Image file path (saved to `posts` table)

**Tech**: OpenRouter API (image generation: DALL-E, Stable Diffusion, etc.)

**Process**:
1. Load approved content from `content_options` table
2. Build image prompt: topic + fact + style preferences
3. Call OpenRouter image generation endpoint
4. Save image to `data/images/` directory
5. Create entry in `posts` table with image path

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

### Module 6: Scheduler
**Purpose**: Post approved content with visual to configured platforms
**Input**: Post entry from `posts` table
**Output**: Updated post status + URL (in `posts` table)

**Tech**: `requests` for platform REST APIs (Pinterest API, Instagram API, etc.)

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
**Purpose**: PostgreSQL connection and query helpers
**Used by**: All modules
**Interface**:
```python
def get_connection() -> psycopg2.connection
def execute(query: str, params: tuple = None) -> list[dict]
def execute_one(query: str, params: tuple = None) -> dict | None
```

### openrouter_client.py
**Purpose**: Single wrapper for all OpenRouter API calls
**Used by**: Modules 2, 3, 5
**Interface**:
```python
def generate_text(prompt: str, model: str = "openai/gpt-4o-mini") -> str
def generate_image(prompt: str, model: str = "dall-e-3") -> bytes
```

### models.py
**Purpose**: Shared data classes for type safety
**Classes**:
```python
@dataclass
class Trend:
    keyword: str
    score: int
    source: str

@dataclass
class Theme:
    trend: str
    theme: str
    category: str

@dataclass
class ContentOption:
    id: int
    batch_id: str
    topic: str
    fact: str
    hashtags: list[str]
    status: str  # pending | approved | posted | expired

@dataclass
class Post:
    id: int
    content_option_id: int
    platform: str
    image_path: str
    status: str  # pending | success | failed
    post_url: str | None
```

## Cron Configuration

```bash
# Run content generation pipeline every 2 hours
0 */2 * * * cd /path/to/did-you-know && python main.py generate >> /var/log/content-generator.log 2>&1
```

## Running the System

```bash
# 1. Run database migrations
python -m shared.migrate

# 2. Start web UI (for approval dashboard)
python -m web.app

# 3. Cron handles automatic generation (every 2 hours)
# Or run manually:
python main.py generate
```

## Environment Variables (.env)
```
DATABASE_URL=postgresql://user:pass@localhost:5432/did_you_know
OPENROUTER_API_KEY=sk-or-...
PINTEREST_ACCESS_TOKEN=...
INSTAGRAM_ACCESS_TOKEN=...
```

# logging_and_cleanup_fixes.md

## 1. Feature Overview
**Purpose**: Fix three issues blocking the `generate` command: (1) noisy Google Trends 404 tracebacks, (2) redundant httpx HTML output polluting stdout, (3) missing file-based logging for pipeline debugging, (4) queue config key mismatch between `content_template.yaml` and `backup_trends.yaml`.

**Business Value**: Enables developers to run `python main.py generate` and get clean, actionable output. Pipeline events are logged to a file for post-mortem debugging.

**Scope**:
- Remove `exc_info=True` from expected Google Trends API failures (404 is normal — fallback chain handles it)
- Suppress `httpx` INFO-level logging (it prints full HTTP response HTML to stdout)
- Add file-based logging with rotation to `logs/pipeline.log`
- Fix queue config: `ContentGenerator` reads `queue` from `content_template` config, but queue settings live in `backup_trends.yaml`

**Success Criteria**:
- `python main.py generate` produces clean stdout (no HTML, no tracebacks for expected failures)
- Pipeline events are written to `logs/pipeline.log` with rotation
- Queue config is correctly read from `backup_trends.yaml`

## 2. Service Ownership
**Primary Service**: `main.py` (entrypoint), `modules/trend_selector.py`, `modules/content_generator.py`, `app/scheduler.py`

**Dependent Services**: None

**Interface Changes**: None (logging is internal)

## 3. Detailed Implementation

### 3.1 Google Trends 404 — Remove `exc_info=True` from expected failures

**File**: `modules/trend_selector.py`

**Lines 119-123** (realtime_trending_searches failure):
```python
# Current:
except Exception:
    logger.warning(
        "realtime_trending_searches() failed; trying trending_searches().",
        exc_info=True,
    )

# Fixed:
except Exception:
    logger.warning(
        "realtime_trending_searches() failed; trying trending_searches()."
    )
```

**Lines 130-134** (trending_searches failure):
```python
# Current:
except Exception:
    logger.warning(
        "trending_searches() also failed; no API trends available.",
        exc_info=True,
    )

# Fixed:
except Exception:
    logger.warning(
        "trending_searches() also failed; no API trends available."
    )
```

**Lines 146-148** (`_parse_trending_searches` inner try/except):
```python
# Current:
except Exception:
    logger.warning("trending_searches() raised an exception.", exc_info=True)
    raise

# Fixed:
except Exception:
    logger.warning("trending_searches() raised an exception.")
    raise
```

**Lines 170-174** (`_parse_realtime_trending` inner try/except):
```python
# Current:
except Exception:
    logger.warning(
        "realtime_trending_searches() raised an exception.", exc_info=True
    )
    raise

# Fixed:
except Exception:
    logger.warning("realtime_trending_searches() raised an exception.")
    raise
```

**Rationale**: These 404 errors are **expected** — the fallback chain is designed to handle them. `exc_info=True` prints the full traceback to stdout, which is noise. The WARNING level message is sufficient.

### 3.2 Suppress httpx INFO logging

**File**: `main.py`

Add after `logging.basicConfig(...)` (around line 26):
```python
# Suppress httpx INFO logging — it prints full HTTP response HTML to stdout
logging.getLogger("httpx").setLevel(logging.WARNING)
```

**Rationale**: `httpx` logs every HTTP request/response at INFO level, including the full response body (HTML). This pollutes stdout when running `python main.py generate`. Setting to WARNING suppresses this noise while still showing actual errors.

### 3.3 File-based logging with rotation

**File**: `main.py`

Add after `logging.basicConfig(...)` and the httpx suppression:

```python
import os
from logging.handlers import RotatingFileHandler

# File-based logging for pipeline debugging
os.makedirs("logs", exist_ok=True)
file_handler = RotatingFileHandler(
    "logs/pipeline.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logging.getLogger().addHandler(file_handler)
```

**Rationale**: A rotating file handler at DEBUG level captures all pipeline events for post-mortem debugging without polluting stdout. The root logger gets the file handler so all modules' logs go there.

### 3.4 Fix queue config key mismatch

**Problem**: `ContentGenerator.__init__` reads `queue` config from `self._config` (which is the `content_template` config dict). But queue settings (`max_pending`, `expire_days`, `cleanup_on_generate`) are defined in `backup_trends.yaml`, not `content_template.yaml`.

**File**: `app/scheduler.py` — `run_pipeline()` function

**Current** (line 116-118):
```python
content_generator = ContentGenerator(
    db_pool, openrouter_client, config.get("content_template", {})
)
```

**Fixed**:
```python
# Merge queue config from backup_trends into content_template config
content_template_config = dict(config.get("content_template", {}))
backup_config = config.get("backup_trends", {})
if "queue" in backup_config:
    content_template_config["queue"] = backup_config["queue"]

content_generator = ContentGenerator(
    db_pool, openrouter_client, content_template_config
)
```

**Rationale**: The `ContentGenerator` expects `queue` settings in its config dict. The queue settings are logically part of the backup_trends config file. Merging them at the scheduler level avoids moving config keys around.

## 4. Error Handling
- **File logging failure**: If `logs/` directory cannot be created or the log file cannot be written, the `RotatingFileHandler` will log to stderr. The application continues to work — file logging is best-effort.
- **httpx suppression**: No error case — it's just a log level change.

## 5. Input/Output Specifications
No API changes. All changes are internal to logging and config merging.

## 6. Edge Cases
- **Logs directory doesn't exist**: `os.makedirs("logs", exist_ok=True)` handles this.
- **Log file grows large**: `RotatingFileHandler` with 5 MB max and 3 backups handles this.
- **Queue config missing from both files**: `ContentGenerator` already has defaults (`max_pending=10`, `expire_days=7`, `cleanup_on_generate=True`).
- **Google Trends API succeeds**: The `exc_info=True` removal doesn't affect success path — only the exception handler changes.

## 7. Dependencies
- `logging.handlers.RotatingFileHandler` — standard library, no new dependencies.

## 8. Testing Requirements
- **Unit tests**: No new tests needed — existing tests cover the behavior.
- **Manual test**: Run `python main.py generate` and verify:
  - No HTML output on stdout
  - No tracebacks for Google Trends 404
  - `logs/pipeline.log` exists and contains pipeline events
  - Pipeline completes successfully

## 9. Deployment Considerations
- **Logs directory**: Created automatically by `os.makedirs("logs", exist_ok=True)`.
- **Log rotation**: Automatic — 5 MB per file, 3 backups.
- **Disk usage**: Max ~20 MB for log files.
- **Rollback**: No migration needed — revert the code changes.
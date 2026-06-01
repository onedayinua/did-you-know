# trend_selector_asyncpg_interval_type_fix.md

## 1. Feature Overview
**Purpose**: Fix a `DataError` crash when `_get_used_keywords()` passes a string `"30 days"` to asyncpg, which expects a Python `datetime.timedelta` object for `interval` parameters.

**Business Value**: The pipeline crashes on every run when Google Trends API is unavailable and the code falls back to backup trends. This fix restores the backup trend fallback path.

**Scope**: One-line change in `modules/trend_selector.py` — replace the string argument with a `timedelta` object.

**Success Criteria**: `python main.py generate` completes without `asyncpg.exceptions.DataError` when using backup trends.

## 2. Service Ownership
**Primary Service**: `modules/trend_selector.py`
**Dependent Services**: None (no interface changes)
**Interface Changes**: None

## 3. Detailed Implementation
### File: `modules/trend_selector.py`

**Change 1 — Add import** (line 15):
```python
from datetime import timedelta
```

**Change 2 — Fix parameter** (line 211):
```python
# Before (broken):
rows = await self._db.fetch(query, f"{days} days")

# After (fixed):
rows = await self._db.fetch(query, timedelta(days=days))
```

## 4. Error Handling
**Expected Failures**: None — `timedelta(days=days)` is a stdlib type that asyncpg natively supports for `interval` columns.

**Recovery Strategies**: N/A — this is a type fix, not a runtime recovery.

## 5. Input/Output Specifications
**Input**: `days: int` (unchanged)
**Output**: `set[str]` (unchanged)

## 6. Edge Cases
- `days=0`: `timedelta(days=0)` works correctly — returns keywords created since `CURRENT_TIMESTAMP` (i.e., none).
- `days` negative: `timedelta(days=-1)` works — would look into the future, but this is a caller bug, not a type bug.

## 7. Dependencies
- `datetime` (stdlib, already available)
- asyncpg (no change required)

## 8. Testing Requirements
- **Unit test**: Mock `self._db.fetch` and verify it's called with a `timedelta` object, not a string.
- **Manual test**: Run `python main.py generate` and confirm no `DataError`.

## 9. Deployment Considerations
- **Migration**: None
- **Rollback**: Revert the two-line change
- **Monitoring**: No new metrics needed

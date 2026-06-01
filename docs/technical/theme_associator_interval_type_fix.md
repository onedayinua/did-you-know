# theme_associator_interval_type_fix.md

## 1. Feature Overview
**Purpose**: Fix the same `DataError` bug in `theme_associator.py` where `f"{hours} hours"` is passed as an `interval` parameter to asyncpg instead of a `timedelta` object.

**Business Value**: The pipeline will crash at step 2 (theme association) after the trend selection fix.

**Scope**: One-line change in `modules/theme_associator.py`.

**Success Criteria**: Pipeline progresses past theme association without `DataError`.

## 2. Service Ownership
**Primary Service**: `modules/theme_associator.py`
**Dependent Services**: None
**Interface Changes**: None

## 3. Detailed Implementation
### File: `modules/theme_associator.py`

**Change 1 — Add import** (around line 14):
```python
from datetime import timedelta
```

**Change 2 — Fix parameter** (line 181):
```python
# Before:
row = await self._db.fetchrow(query, f"{hours} hours", theme_name)

# After:
row = await self._db.fetchrow(query, timedelta(hours=hours), theme_name)
```

## 4. Error Handling
Same as TKT-002 — `timedelta` is natively supported by asyncpg.

## 5. Testing Requirements
- **Manual test**: Run `python main.py generate` and confirm no `DataError`.

## 6. Deployment Considerations
- **Migration**: None
- **Rollback**: Revert the two-line change
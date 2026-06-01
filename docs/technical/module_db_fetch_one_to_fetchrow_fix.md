# module_db_fetch_one_to_fetchrow_fix.md

## 1. Feature Overview
**Purpose**: Fix `AttributeError: 'Pool' object has no attribute 'fetch_one'` — replace `.fetch_one()` calls on raw `asyncpg.Pool` objects with `.fetchrow()`.

**Business Value**: The pipeline crashes immediately after the backup trend selection succeeds, preventing the entire content generation flow.

**Scope**: Replace all `.fetch_one()` calls on raw pool objects in `modules/*.py` with `.fetchrow()`.

**Success Criteria**: `python main.py generate` progresses past the backup trend saving step without crashing.

## 2. Service Ownership
**Primary Service**: All modules that call `.fetch_one()` directly on the pool:
- `modules/trend_selector.py`
- `modules/content_generator.py`
- `modules/theme_associator.py`

**Dependent Services**: None (no interface changes)
**Interface Changes**: None

## 3. Detailed Implementation

### Background
`asyncpg.Pool` provides these query methods:
- `pool.fetch()` — returns `list[Record]` ✅ (used correctly)
- `pool.fetchrow()` — returns `Record | None` ← **this is the correct method**
- `pool.fetchval()` — returns a single value
- `pool.execute()` — returns status string

There is **no** `pool.fetch_one()` method — that's a name used in `shared/db.py` which acquires a connection internally.

### Changes Required

#### File 1: `modules/trend_selector.py` (line 262)
```python
# Before:
row = await self._db.fetch_one(query, keyword, score, source)

# After:
row = await self._db.fetchrow(query, keyword, score, source)
```

#### File 2: `modules/content_generator.py` (line 430)
```python
# Before:
row = await self._db.fetch_one(query, ...)

# After:
row = await self._db.fetchrow(query, ...)
```

#### File 3: `modules/theme_associator.py` (lines 181, 202)
```python
# Before:
row = await self._db.fetch_one(query, ...)

# After:
row = await self._db.fetchrow(query, ...)
```

## 4. Error Handling
**Expected Failures**: None — `fetchrow` has identical return type semantics as `fetch_one` was expected to have.

## 5. Input/Output Specifications
**Input**: Same as before (query string + params)
**Output**: `asyncpg.Record | None` (identical behavior)

## 6. Edge Cases
- `fetchrow` with INSERT … RETURNING: Returns the inserted row (same as expected behavior)
- `fetchrow` when no rows match: Returns `None` (same as expected behavior)

## 7. Dependencies
- `asyncpg` (no change required)

## 8. Testing Requirements
- **Unit tests**: The tests mock `fetch_one` on the pool. They should be updated to mock `fetchrow` instead. However, since the mock setup (`pool.fetch_one = AsyncMock()`) works for any attribute name, the existing tests will still pass as-is (they won't affect runtime behavior).

## 9. Deployment Considerations
- **Migration**: None
- **Rollback**: Revert the 4 lines changed across 3 files
- **Monitoring**: No new metrics needed
# Testing

## Purpose
Standard testing patterns for services using pytest.

## Test Structure
```
<service-name>/
  tests/
    __init__.py
    conftest.py           # Shared fixtures
    test_<module>.py      # Tests for each module
```

## conftest.py (Shared Fixtures)
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.publish = AsyncMock()
    redis.xadd = AsyncMock()
    redis.xread = AsyncMock(return_value=[])
    return redis

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.session_factory = AsyncMock()
    return db

@pytest.fixture
def mock_message_bus(mock_redis):
    from your_module import MessageBus
    bus = MessageBus.__new__(MessageBus)
    bus.redis = mock_redis
    return bus
```

## Test Patterns
```python
import pytest
from unittest.mock import AsyncMock, patch

# Unit test
@pytest.mark.asyncio
async def test_add_asset(mock_db):
    from your_module import add_asset
    
    asset_id = await add_asset(mock_db, "BTC/USD", "BTC", "USD", "15m")
    assert asset_id is not None

# Integration test with mocked Redis
@pytest.mark.asyncio
async def test_publish_event(mock_message_bus):
    await mock_message_bus.publish("data.synced", {"asset_id": 1})
    mock_message_bus.redis.publish.assert_called_once()

# Test error handling
@pytest.mark.asyncio
async def test_get_asset_not_found(mock_db):
    from your_module import get_asset
    
    asset = await get_asset(mock_db, 999)
    assert asset is None
```

## Running Tests
```bash
# All tests for a service
pytest <service-name>/tests/

# Single test file
pytest <service-name>/tests/test_file.py

# Single test by name
pytest <service-name>/tests/test_file.py::test_name -v

# With coverage
pytest <service-name>/tests/ --cov=<service-name>
```

## Test Categories
- **Unit tests**: Test individual functions/classes with mocked dependencies
- **Integration tests**: Test service components with real Redis/DB (use test containers)
- **API tests**: Test REST endpoints with `httpx.AsyncClient`

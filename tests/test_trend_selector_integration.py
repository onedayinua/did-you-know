"""Integration test that actually calls the Google Trends RSS feed."""
import pytest
import pytest_asyncio
from modules.trend_selector import TrendSelector

@pytest.mark.integration
@pytest.mark.asyncio
async def test_rss_feed_returns_real_trends():
    """Actually calls the Google Trends RSS feed and verifies it returns data."""
    selector = TrendSelector(None, {"geo": "US"})

    results = await selector._fetch_trends()

    assert len(results) > 0, "RSS feed should return at least 1 trend"
    assert all("keyword" in r for r in results)
    assert all("score" in r for r in results)
    assert all(r["score"] > 0 for r in results)
    assert all(len(r["keyword"]) > 0 for r in results)
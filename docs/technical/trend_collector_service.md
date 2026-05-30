# Trend Collector Service

## 1. Feature Overview
**Purpose**: Daily cron service to fetch trending food-related queries from Google Trends
**Business Value**: Provides up-to-date trending topics for content creation
**Scope**: Fetch trending search queries, store in database, trigger content pipeline
**Success Criteria**: Daily execution with at least 10 trending queries stored, 95% success rate

## 2. Service Ownership
**Primary Service**: `trend-collector-service`
**Dependent Services**: Content Pipeline Service (triggered via REST API)
**Interface Changes**: New REST endpoint `/api/v1/trends/process` for triggering content pipeline

## 3. Detailed Implementation

### Database Changes
**Updates to trends table**:
- Add columns for API source and fetch metadata
- Add indexes for daily processing queries

```sql
-- Migration: 0002_add_trend_collector_metadata.sql
ALTER TABLE trends ADD COLUMN source VARCHAR(50) DEFAULT 'google_trends';
ALTER TABLE trends ADD COLUMN fetch_metadata JSONB DEFAULT '{}';
ALTER TABLE trends ADD COLUMN processed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;
ALTER TABLE trends ADD COLUMN processing_error TEXT DEFAULT NULL;

CREATE INDEX idx_trends_source ON trends(source);
CREATE INDEX idx_trends_processed_at ON trends(processed_at DESC);
CREATE INDEX idx_trends_processing_error ON trends(processing_error) WHERE processing_error IS NOT NULL;
```

### API Endpoints
**Internal REST API**:
```python
# POST /api/v1/trends
# Create new trend entry from Google Trends data
Request:
{
    "query": "string",
    "trend_score": "float",
    "region": "string",
    "source": "google_trends",
    "fetch_metadata": {
        "search_volume": "int",
        "growth_rate": "float",
        "relative_interest": "float"
    }
}

Response:
{
    "id": "uuid",
    "query": "string",
    "status": "success|error",
    "error": "string | null"
}

# POST /api/v1/trends/process
# Trigger content pipeline for specific trend
Request:
{
    "trend_id": "uuid",
    "query": "string"
}

Response:
{
    "trend_id": "uuid",
    "content_pipeline_triggered": "boolean",
    "pipeline_job_id": "string | null"
}
```

### Cron Job Configuration
```yaml
# config/cron.yaml
jobs:
  - name: daily_trend_collection
    schedule: "0 0 * * *"  # Daily at midnight UTC
    command: "python trend_collector.py --days 1 --region US --category food"
    max_runtime: 1800  # 30 minutes
    retry_policy:
      max_attempts: 3
      backoff_factor: 2
      initial_delay: 60
```

### Service Structure
```
trend-collector-service/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── collector.py         # Google Trends API client
│   ├── database.py          # Database operations
│   ├── scheduler.py         # Cron job management
│   └── config.py           # Configuration management
├── scripts/
│   └── trend_collector.py  # Cron executable
├── tests/
│   ├── test_collector.py
│   └── test_integration.py
├── requirements.txt
└── Dockerfile
```

### Google Trends API Integration
```python
class GoogleTrendsClient:
    def __init__(self, api_key: str, region: str = "US"):
        self.api_key = api_key
        self.region = region
        self.base_url = "https://trends.google.com/trends/api"
    
    async def fetch_daily_trends(self, category: str = "food", days: int = 1):
        """Fetch trending queries for specified category"""
        params = {
            "hl": "en-US",
            "tz": "-180",
            "cat": self._map_category(category),
            "geo": self.region,
            "date": f"now {days}-d"
        }
        
        # Make request with exponential backoff
        trends = await self._make_request_with_retry("/dailytrends", params)
        
        # Extract and normalize trends
        normalized = self._normalize_trends(trends)
        return normalized
```

## 4. Error Handling
**Expected Failures**:
- Google Trends API rate limiting (429 status)
- API key expiration or invalidation
- Network timeouts (30s timeout)
- Database connection failures
- Content pipeline service unavailable

**Recovery Strategies**:
- Rate limiting: Exponential backoff with jitter (max 5 retries)
- API key issues: Log alert and continue with cached data
- Network timeouts: Retry with increasing delays
- Database failures: Queue trends in Redis for later processing
- Content pipeline unavailable: Store trend as pending for manual trigger

**Error Responses**:
```json
{
    "error": {
        "code": "RATE_LIMITED|API_ERROR|NETWORK_ERROR|DB_ERROR",
        "message": "Detailed error message",
        "retry_after": 300,
        "trends_collected": 5
    }
}
```

**Logging Requirements**:
- INFO: Daily collection started/completed
- WARNING: API rate limiting encountered
- ERROR: Failed to collect trends
- DEBUG: Individual trend processing details

## 5. Input/Output Specifications
**Input Validation**:
- `days`: integer, 1-30
- `region`: string, ISO country code
- `category`: string, must be in ["food", "recipes", "cooking", "nutrition"]
- `min_score`: float, 0.0-100.0, default 50.0

**Output Formats**:
```json
{
    "execution_id": "uuid",
    "start_time": "2024-01-15T00:00:00Z",
    "end_time": "2024-01-15T00:05:30Z",
    "trends_collected": 15,
    "trends_persisted": 15,
    "pipeline_triggered": 15,
    "failed_collections": 0,
    "average_score": 72.5
}
```

## 6. Edge Cases
- Google Trends returns empty results for category
- Duplicate trending queries across multiple days
- Seasonal variations in trending data (holidays)
- API returns malformed JSON or HTML instead of JSON
- Concurrent cron job executions
- System timezone vs UTC discrepancies
- Daylight saving time transitions

## 7. Dependencies
- **Google Trends API**: Unofficial API or pytrends library
- **PostgreSQL**: For trend storage
- **Redis**: For rate limiting cache and job queues
- **FastAPI**: REST API framework
- **APScheduler**: Cron scheduling library
- **Requests/httpx**: HTTP client with retry support

## 8. Testing Requirements
- **Unit tests**: Google Trends API client with mocked responses
- **Integration tests**: Full collection flow with test database
- **Performance tests**: Measure API call latency and throughput
- **Error handling tests**: Simulate API failures and rate limiting
- **Concurrency tests**: Multiple simultaneous cron jobs

## 9. Deployment Considerations
- **Migration**: Run schema updates before service deployment
- **Rollback**: Service can run with older schema version
- **Monitoring**:
  - Metric: `trend_collector_executions_total`
  - Metric: `trends_collected_per_day`
  - Metric: `collection_duration_seconds`
  - Alert: Collection failure for 2 consecutive days
- **Performance**: Max 1000 API calls per day, 10 concurrent collections
- **Security**: API keys stored in environment variables, not in code
- **Cost**: Free tier of Google Trends API (rate limited)
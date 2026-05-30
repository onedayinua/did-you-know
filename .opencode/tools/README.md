# Database Connection Tool for OpenCode Agents

This tool provides safe, read-only access to any service's database for debugging and development purposes.

## Features

- **Generic service-agnostic design**: Connect to any service's database
- **Safe read-only access**: Only SELECT queries are allowed
- **SQL injection protection**: Validates all inputs and uses parameterized queries
- **Async operations**: Uses async/await for database operations
- **Path resolution**: Automatically resolves relative database paths
- **Multiple connection methods**: Use service name OR direct database URL

## Installation

The tool is automatically available to OpenCode agents. It uses the project's shared database module and service configuration.

## Usage

### Basic Usage

```python
from .opencode.tools.database_tool import DatabaseTool

# Create tool instance for a specific service
db_tool = DatabaseTool(service_name="data-service")

# OR create tool with direct database URL
db_tool = DatabaseTool(database_url="sqlite+aiosqlite:///./mltscr.db")

# Initialize connection
await db_tool.initialize()

# Run queries
results = await db_tool.query("SELECT * FROM assets LIMIT 5")

# Close connection
await db_tool.close()
```

### Using Context Manager

```python
from .opencode.tools.database_tool import DatabaseTool

async with DatabaseTool(service_name="data-service") as db_tool:
    results = await db_tool.query("SELECT * FROM assets")
    # Connection automatically closed
```

### Built-in Methods

#### List Tables
```python
tables = await db_tool.list_tables()
# Returns: ['assets', 'ohlcv']
```

#### Get Table Schema
```python
schema = await db_tool.get_table_schema("ohlcv")
# Returns column information for ohlcv table
```

#### Get Row Count
```python
count = await db_tool.get_row_count("assets")
# Returns: 42
```

#### Get Database Statistics
```python
stats = await db_tool.get_database_stats()
# Returns: {"tables": [...], "table_counts": {...}}
```

#### Execute and Print
```python
await db_tool.execute_and_print("SELECT * FROM assets LIMIT 3")
# Prints formatted table output
```

### Raw SQL Queries

```python
# Safe SELECT query
results = await db_tool.query(
    "SELECT * FROM assets WHERE is_active = :active",
    {"active": True}
)

# This will raise ValueError (non-SELECT query)
try:
    await db_tool.query("DELETE FROM assets")
except ValueError as e:
    print(f"Blocked: {e}")
```

## Service-Agnostic Connection

The tool can connect to any service's database:

```python
# Connect to different services
db_tool = DatabaseTool(service_name="data-service")
db_tool = DatabaseTool(service_name="trading-service")
db_tool = DatabaseTool(service_name="feature-service")
db_tool = DatabaseTool(service_name="model-service")

# Or use direct URL
db_tool = DatabaseTool(database_url="sqlite+aiosqlite:///./data-service/mltscr.db")
```

## Security Features

1. **Read-only enforcement**: Blocks INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, etc.
2. **SQL injection protection**: 
   - Validates table names with regex
   - Uses parameterized queries
   - Checks for dangerous keywords
3. **Input validation**: All inputs are validated before use
4. **Table existence checks**: Verifies tables exist before querying them

## Error Handling

The tool provides informative error messages:

```python
try:
    await db_tool.query("DROP TABLE assets")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Query contains non-read-only keyword: DROP. Only SELECT queries are allowed.
```

## Configuration

The tool automatically loads configuration from `<service>/.env`:

```bash
DATABASE_URL=sqlite+aiosqlite:///./mltscr.db
```

## Testing

Run the tool directly to test:

```bash
cd /workspaces/mltscr
source cenv/bin/activate
python .opencode/tools/database_tool.py
```

## Limitations

1. **SQLite-specific**: Uses SQLite-specific queries (PRAGMA, sqlite_master)
2. **Read-only**: Cannot modify data (by design)
3. **Async only**: Requires async context
4. **Service dependency**: Requires the target service's .env file and database

## Common Debugging Scenarios

### 1. Check Database Health
```python
stats = await db_tool.get_database_stats()
print(f"Tables: {stats['tables']}")
print(f"Row counts: {stats['table_counts']}")
```

### 2. Inspect Table Structure
```python
schema = await db_tool.get_table_schema("ohlcv")
for col in schema:
    print(f"{col['name']}: {col['type']} {'(PK)' if col['primary_key'] else ''}")
```

### 3. View Recent Data
```python
# Get latest records from any table
await db_tool.execute_and_print("SELECT * FROM ohlcv ORDER BY timestamp DESC LIMIT 10")
```

### 4. Check Data Quality
```python
# Count null values in a column
result = await db_tool.query(
    "SELECT COUNT(*) as null_count FROM ohlcv WHERE close IS NULL"
)
print(f"Null close prices: {result[0]['null_count']}")
```

## Integration with OpenCode Agents

Agents can use this tool to:
- Debug database issues during development
- Verify data quality
- Inspect schema changes
- Monitor data ingestion
- Validate test data
- Work with ANY service's database

## Migration from Old Version

The old version was hardcoded to data-service. To migrate:

**Old (deprecated)**:
```python
db_tool = DatabaseTool()  # Only works with data-service
assets = await db_tool.get_assets()  # Business logic method
ohlcv = await db_tool.get_ohlcv("BTCUSDT")  # Business logic method
```

**New (recommended)**:
```python
db_tool = DatabaseTool(service_name="data-service")  # Specify service
tables = await db_tool.list_tables()  # Generic table listing
results = await db_tool.query("SELECT * FROM assets")  # Raw SQL queries
```

**Deprecation warnings** will be shown for old usage patterns.

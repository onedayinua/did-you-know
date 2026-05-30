#!/usr/bin/env python3
"""
Example usage of the Database Connection Tool for OpenCode agents.

This shows how agents can use the tool to debug and inspect database tables
for any service in the project.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import the database tool
import importlib.util
spec = importlib.util.spec_from_file_location(
    "database_tool", 
    str(Path(__file__).parent / "database_tool.py")
)
database_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_tool)
DatabaseTool = database_tool.DatabaseTool


async def example_basic_usage():
    """
    Example of basic database inspection using the generic tool.
    """
    print("🔍 Starting database inspection...")
    
    # Option 1: Use service name (recommended for most cases)
    db_tool = DatabaseTool(service_name="data-service", echo=False)
    
    try:
        # 1. Quick database health check
        print("\n1. Database Health Check:")
        stats = await db_tool.get_database_stats()
        print(f"   Tables: {', '.join(stats['tables'])}")
        for table, count in stats['table_counts'].items():
            print(f"   - {table}: {count} rows")
        
        # 2. Inspect table structures
        print("\n2. Table Structures:")
        for table in stats['tables']:
            schema = await db_tool.get_table_schema(table)
            print(f"   {table}:")
            for col in schema[:3]:  # Show first 3 columns
                pk = " (PK)" if col.get('primary_key', 0) else ""
                nullable = " NULL" if col.get('nullable', True) else " NOT NULL"
                print(f"     - {col['name']}: {col['type']}{pk}{nullable}")
            if len(schema) > 3:
                print(f"     ... and {len(schema) - 3} more columns")
        
        # 3. Sample data from each table
        print("\n3. Sample Data:")
        for table in stats['tables'][:2]:  # Show first 2 tables
            print(f"\n   {table} (first 3 rows):")
            sql = f"SELECT * FROM {table} LIMIT 3"
            await db_tool.execute_and_print(sql)
        
        # 4. Example of safe raw query
        print("\n4. Custom Query Example:")
        await db_tool.execute_and_print(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        
        print("\n✅ Inspection completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Inspection failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await db_tool.close()


async def example_direct_url():
    """
    Example of using a direct database URL.
    """
    print("\n" + "=" * 60)
    print("Example: Using Direct Database URL")
    print("=" * 60)
    
    # Option 2: Use direct database URL
    db_tool = DatabaseTool(
        database_url="sqlite+aiosqlite:///./data-service/mltscr.db",
        echo=False
    )
    
    try:
        print("\n1. List Tables:")
        tables = await db_tool.list_tables()
        print(f"   Tables: {', '.join(tables)}")
        
        if 'assets' in tables:
            print("\n2. Assets Table Schema:")
            schema = await db_tool.get_table_schema("assets")
            for col in schema:
                print(f"   - {col['name']}: {col['type']}")
            
            print("\n3. Row Count:")
            count = await db_tool.get_row_count("assets")
            print(f"   Total assets: {count}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await db_tool.close()


async def example_data_quality_check():
    """
    Example of data quality checks an agent might perform.
    """
    print("\n" + "=" * 60)
    print("Example: Data Quality Checks")
    print("=" * 60)
    
    db_tool = DatabaseTool(service_name="data-service", echo=False)
    
    try:
        stats = await db_tool.get_database_stats()
        
        # Check for null values in critical columns
        print("\n1. Checking for null values:")
        checks = [
            ("ohlcv", "close", "Close price should never be null"),
            ("ohlcv", "timestamp", "Timestamp should never be null"),
        ]
        
        for table, column, description in checks:
            if table not in stats['tables']:
                continue
            try:
                result = await db_tool.query(
                    f"SELECT COUNT(*) as null_count FROM {table} WHERE {column} IS NULL"
                )
                null_count = result[0]['null_count'] if result else 0
                status = "✅" if null_count == 0 else "⚠️"
                print(f"   {status} {description}: {null_count} null values")
            except Exception as e:
                print(f"   ❌ Failed to check {table}.{column}: {e}")
                
    finally:
        await db_tool.close()


async def example_service_agnostic():
    """
    Example showing the tool works with any service.
    """
    print("\n" + "=" * 60)
    print("Example: Service-Agnostic Tool")
    print("=" * 60)
    
    print("\nThe DatabaseTool can now connect to ANY service:")
    print("  - DatabaseTool(service_name='data-service')")
    print("  - DatabaseTool(service_name='trading-service')")
    print("  - DatabaseTool(service_name='feature-service')")
    print("  - DatabaseTool(service_name='model-service')")
    print("  - DatabaseTool(database_url='path/to/your/db')")
    
    # Try with different services (will show which ones exist)
    services_to_check = [
        "data-service",
        "trading-service",
        "feature-service",
        "model-service",
    ]
    
    print("\nChecking available services:")
    project_root = Path("/workspaces/mltscr")
    for service in services_to_check:
        service_path = project_root / service
        has_env = (service_path / ".env").exists() or (service_path / ".env.test").exists()
        status = "✅" if has_env else "❌"
        print(f"  {status} {service}")


if __name__ == "__main__":
    print("=" * 60)
    print("Database Connection Tool - Example Usage for Agents")
    print("=" * 60)
    
    # Run examples
    asyncio.run(example_basic_usage())
    asyncio.run(example_direct_url())
    asyncio.run(example_data_quality_check())
    asyncio.run(example_service_agnostic())
    
    print("\n" + "=" * 60)
    print("Examples completed. Agents can use these patterns for debugging.")
    print("=" * 60)

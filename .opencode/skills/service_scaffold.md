# Service Scaffold

## Purpose
Standard structure and entry point for every service in the system.

## Required Structure
```
<service-name>/
  main.py              # Entry point: handles SIGTERM, starts service
  .env                 # Configuration (loaded at startup)
  requirements.txt     # Service-specific dependencies
  tests/               # pytest tests
```

## main.py Requirements
- Accept `run` as the only subcommand: `python main.py run`
- Handle SIGTERM for graceful shutdown (close DB, drain Redis, cleanup)
- Load config from `.env` using `python-dotenv`
- Connect to Redis (pub/sub + streams) and PostgreSQL on startup
- Publish heartbeat messages at configured intervals
- Register with Health Service on startup

## Example main.py
```python
import asyncio
import signal
import sys
from dotenv import load_dotenv

class Service:
    def __init__(self):
        load_dotenv()
        self._shutdown = asyncio.Event()
        self.redis = None
        self.db = None

    async def start(self):
        # Connect to Redis and PostgreSQL
        # Register with Health Service
        # Start heartbeat loop
        pass

    async def stop(self):
        # Close DB connections
        # Drain Redis streams
        # Cleanup resources
        pass

    async def run(self):
        await self.start()
        await self._shutdown.wait()
        await self.stop()

    def _handle_signal(self):
        self._shutdown.set()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        service = Service()
        loop = asyncio.new_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, service._handle_signal)
        loop.run_until_complete(service.run())
        loop.close()
    else:
        print("Usage: python main.py run")
        sys.exit(1)
```

## Configuration
- `.env` file per service with defaults in code
- Required config values validated at startup
- Missing required config → exit with clear error message

## Required .env Variables (all services)
```
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
HEARTBEAT_INTERVAL=30
SERVICE_NAME=<service-name>
LOG_LEVEL=INFO
```

# Database Models

## Purpose
Standard patterns for async database access with SQLAlchemy.

## Model Definition
```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    base_currency = Column(String(10), nullable=False)
    quote_currency = Column(String(10), nullable=False)
    timeframe = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class OHLCV(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    source = Column(String(50))
```

## Async Database Connection
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def connect(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()

    async def get_session(self):
        async with self.session_factory() as session:
            yield session
```

## Query Patterns
```python
from sqlalchemy import select

async def get_asset(db: Database, asset_id: int):
    async with db.session_factory() as session:
        result = await session.execute(select(Asset).where(Asset.id == asset_id))
        return result.scalar_one_or_none()

async def list_assets(db: Database):
    async with db.session_factory() as session:
        result = await session.execute(select(Asset).where(Asset.is_active == True))
        return result.scalars().all()

async def add_asset(db: Database, symbol: str, base: str, quote: str, timeframe: str):
    async with db.session_factory() as session:
        asset = Asset(symbol=symbol, base_currency=base, quote_currency=quote, timeframe=timeframe)
        session.add(asset)
        await session.commit()
        return asset.id
```

## Migrations
- Use Alembic for schema migrations
- Migration files in `<service>/migrations/`
- Run migrations on service startup or via CLI command

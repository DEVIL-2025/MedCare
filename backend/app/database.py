import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from backend.app.config import settings

logger = logging.getLogger("MedCareControlTower")


class Base(DeclarativeBase):
    pass


# PostgreSQL-only engine and session factory
_active_url = settings.async_database_url

engine = create_async_engine(
    _active_url,
    echo=False,
    future=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def check_db_health() -> bool:
    """Tests live connectivity to the PostgreSQL database."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"[Database] PostgreSQL health check failed: {type(e).__name__} - {e}")
        return False


async def init_database():
    """
    Initializes database tables on the configured PostgreSQL database.
    PostgreSQL is the sole data source. No fallback to SQLite or demo data is permitted.
    """
    safe_url = _active_url.split("@")[-1] if "@" in _active_url else _active_url
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"[Database] Connected successfully to PostgreSQL database: {safe_url}")
    except Exception as e:
        # If tables already exist in PostgreSQL, test connectivity directly
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            logger.info(f"[Database] Verified live connection to PostgreSQL database: {safe_url}")
        except Exception as verify_err:
            logger.error(
                f"[Database] CRITICAL: Failed to connect to PostgreSQL database ({type(verify_err).__name__}: {verify_err}).\n"
                f"==> Target PostgreSQL endpoint: {safe_url}\n"
                "==> PostgreSQL is mandatory. No SQLite, mock, or fallback database will be created."
            )
            raise ConnectionError(f"PostgreSQL connection failed: {verify_err}") from verify_err


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI database session dependency for PostgreSQL."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

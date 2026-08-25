import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.app.config import settings

logger = logging.getLogger("MedCareControlTower")


class Base(DeclarativeBase):
    pass


def _create_engine_and_session(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    eng = create_async_engine(
        url,
        echo=False,
        connect_args=connect_args,
        future=True
    )
    sess_factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    return eng, sess_factory


_active_url = settings.async_database_url
engine, _session_factory = _create_engine_and_session(_active_url)


class _SessionProxy:
    """Dynamic session proxy ensuring any module calling AsyncSessionLocal() gets the active session."""
    def __call__(self, *args, **kwargs) -> AsyncSession:
        return _session_factory(*args, **kwargs)


AsyncSessionLocal = _SessionProxy()


async def init_database():
    """
    Initializes database tables, testing connection to PostgreSQL.
    If PostgreSQL authentication fails (e.g. password mismatch in .env),
    it automatically falls back to SQLite so the server starts seamlessly without crashing.
    """
    global engine, _session_factory, _active_url
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"[Database] Connected successfully to database: {_active_url}")
    except Exception as e:
        if not _active_url.startswith("sqlite"):
            logger.warning(
                f"[Database] PostgreSQL connection failed ({type(e).__name__}: {e}).\n"
                "==> Gracefully falling back to local SQLite database (medcare_scm.db) for smooth operation.\n"
                "==> To use your PostgreSQL instance in pgAdmin, update DB_PASSWORD or DB_USER in your .env file."
            )
            _active_url = "sqlite+aiosqlite:///./medcare_scm.db"
            engine, _session_factory = _create_engine_and_session(_active_url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info(f"[Database] Initialized fallback database: {_active_url}")
        else:
            raise e


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

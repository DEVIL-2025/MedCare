import pytest
import pytest_asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

TEST_DB_FILE = "./test_medcare.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

import backend.app.database as db_module
from backend.app.database import Base
from backend.app.utils.data_seeder import seed_database

# Override global database engine during pytest test session
db_module.engine = test_engine
db_module.AsyncSessionLocal = TestSessionLocal


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Initializes database tables and seeds demo records for the test session.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        await seed_database(session, force=True)
    
    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

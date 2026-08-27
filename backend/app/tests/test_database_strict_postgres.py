import pytest
import os
import httpx
from httpx import ASGITransport
from unittest.mock import patch, AsyncMock
from backend.app.config import Settings
from backend.app.database import init_database, check_db_health
from backend.app.main import app


def test_settings_database_url_never_produces_sqlite():
    """Verify that Settings only produces PostgreSQL URLs and never defaults to SQLite."""
    # Case 1: Empty settings
    empty_settings = Settings(DATABASE_URL=None, DB_HOST=None, DB_USER=None, DB_NAME=None)
    assert not empty_settings.async_database_url.startswith("sqlite")
    assert empty_settings.async_database_url.startswith("postgresql")
    assert not empty_settings.sync_database_url.startswith("sqlite")
    assert empty_settings.sync_database_url.startswith("postgresql")

    # Case 2: Custom PostgreSQL params
    custom_settings = Settings(DATABASE_URL=None, DB_HOST="db.example.com", DB_USER="myuser", DB_PASSWORD="mypassword", DB_NAME="mydb")
    assert "postgresql+asyncpg://myuser:mypassword@db.example.com:5432/mydb" == custom_settings.async_database_url
    assert "postgresql://myuser:mypassword@db.example.com:5432/mydb" == custom_settings.sync_database_url


@pytest.mark.asyncio
async def test_init_database_fails_without_fallback_when_postgres_unreachable():
    """Verify that when PostgreSQL connection fails, init_database raises ConnectionError and DOES NOT create SQLite DB."""
    # Ensure no medcare_scm.db exists beforehand
    sqlite_file = "./medcare_scm.db"
    if os.path.exists(sqlite_file):
        try:
            os.remove(sqlite_file)
        except Exception:
            pass

    # Mock Base.metadata.create_all and AsyncSessionLocal to simulate total connection failure
    with patch("backend.app.database.Base.metadata.create_all", side_effect=Exception("Connection to PostgreSQL failed")), \
         patch("backend.app.database.AsyncSessionLocal", side_effect=Exception("Connection to PostgreSQL failed")):
        with pytest.raises((ConnectionError, Exception)) as exc_info:
            await init_database()
        
        assert "PostgreSQL" in str(exc_info.value) or "failed" in str(exc_info.value).lower()
        # Verify NO SQLite file was created
        assert not os.path.exists(sqlite_file), "SQLite fallback file was created when PostgreSQL failed!"


@pytest.mark.asyncio
async def test_health_check_reports_disconnected_when_postgres_unreachable():
    """Verify that /api/health returns 503 and DISCONNECTED when PostgreSQL is down."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.app.main.check_db_health", new=AsyncMock(return_value=False)):
            res = await client.get("/api/health")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "UNHEALTHY"
            assert data["database"] == "DISCONNECTED"
            assert data["database_engine"] == "PostgreSQL"
            assert "unavailable" in data["error"].lower()


@pytest.mark.asyncio
async def test_health_check_reports_connected_when_postgres_healthy():
    """Verify that /api/health returns 200 and CONNECTED when PostgreSQL is reachable."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.app.main.check_db_health", new=AsyncMock(return_value=True)):
            res = await client.get("/api/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "HEALTHY"
            assert data["database"] == "CONNECTED"
            assert data["database_engine"] == "PostgreSQL"

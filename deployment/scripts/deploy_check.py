#!/usr/bin/env python3
"""
==============================================================================
MedCare Pharma SCM Control Tower - Pre-Flight Deployment Health Check
==============================================================================
Runs automated validation checks across all subsystems:
1. Python runtime & core dependencies
2. Environment configuration
3. Database connectivity (PostgreSQL / SQLite fallback)
4. Machine Learning model artifact & prediction pipeline
5. FastAPI application endpoints & health routes
6. Frontend build directory status
"""

import sys
import os
import asyncio
import logging

import sys
import os
import asyncio
import logging

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DeployCheck")

PASS_ICON = "[PASS]"
FAIL_ICON = "[FAIL]"
WARN_ICON = "[WARN]"


def check_python_version():
    logger.info("\n[1/6] Checking Python Environment...")
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    if major == 3 and minor >= 10:
        logger.info(f"  {PASS_ICON} Python version {version_str} meets requirements (>= 3.10).")
        return True
    else:
        logger.error(f"  {FAIL_ICON} Python version {version_str} is unsupported. Python 3.10+ required.")
        return False


def check_dependencies():
    logger.info("\n[2/6] Checking Critical Python Dependencies...")
    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "aiosqlite",
        "asyncpg",
        "sklearn",
        "pandas",
        "numpy",
        "joblib"
    ]
    all_ok = True
    for pkg in required_packages:
        try:
            __import__(pkg)
            logger.info(f"  {PASS_ICON} Package '{pkg}' is installed.")
        except ImportError as e:
            logger.error(f"  {FAIL_ICON} Missing package: '{pkg}' ({e})")
            all_ok = False
    return all_ok


async def check_database_connection():
    logger.info("\n[3/6] Checking Database Connectivity & Schema Initialization...")
    try:
        from backend.app.config import settings
        from backend.app.database import init_database, AsyncSessionLocal, engine
        from sqlalchemy import text

        logger.info(f"  --> Target Async Database: {settings.async_database_url}")
        await init_database()

        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            val = result.scalar()
            if val == 1:
                logger.info(f"  {PASS_ICON} Database connected and executed ping query successfully.")
                return True
            else:
                logger.error(f"  {FAIL_ICON} Database query returned unexpected result: {val}")
                return False
    except Exception as e:
        logger.error(f"  {FAIL_ICON} Database connection check failed: {e}")
        return False


async def check_ml_model():
    logger.info("\n[4/6] Checking Machine Learning Model Artifact & Pipeline...")
    try:
        from backend.app.ml.train import MODEL_FILE, ModelTrainingService
        from backend.app.ml.predict import PredictionService
        from backend.app.database import AsyncSessionLocal

        if os.path.exists(MODEL_FILE):
            size_kb = os.path.getsize(MODEL_FILE) / 1024
            logger.info(f"  {PASS_ICON} Saved ML model found at: {MODEL_FILE} ({size_kb:.1f} KB)")
        else:
            logger.warning(f"  {WARN_ICON} Model file not found at {MODEL_FILE}. Attempting quick initial training...")
            async with AsyncSessionLocal() as session:
                await ModelTrainingService.train_and_persist_model(session)
            logger.info(f"  {PASS_ICON} Model successfully trained and persisted.")

        async with AsyncSessionLocal() as session:
            model, metadata = await PredictionService.get_or_load_model(session)
            if model is not None:
                features = metadata.get("features", [])
                logger.info(f"  {PASS_ICON} ML Model loaded into memory successfully with {len(features)} input features.")
                return True
            else:
                logger.error(f"  {FAIL_ICON} ML Model could not be loaded into memory.")
                return False
    except Exception as e:
        logger.error(f"  {FAIL_ICON} ML subsystem verification failed: {e}")
        return False


def check_fastapi_app():
    logger.info("\n[5/6] Checking FastAPI App & Route Integrity...")
    try:
        from backend.app.main import app
        route_count = len(app.routes)
        logger.info(f"  {PASS_ICON} FastAPI app '{app.title}' (v{app.version}) loaded with {route_count} registered endpoints.")
        return True
    except Exception as e:
        logger.error(f"  {FAIL_ICON} FastAPI initialization failed: {e}")
        return False


def check_frontend_dist():
    logger.info("\n[6/6] Checking Frontend Production Build Assets...")
    frontend_dist = os.path.join(PROJECT_ROOT, "medcare-frontend", "dist")
    index_html = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_html):
        size_kb = os.path.getsize(index_html) / 1024
        logger.info(f"  {PASS_ICON} Frontend production build found in 'medcare-frontend/dist' (index.html: {size_kb:.2f} KB).")
        return True
    else:
        logger.warning(f"  {WARN_ICON} 'medcare-frontend/dist' not found. For fullstack/static deployment, run 'npm run build' in medcare-frontend.")
        return True  # Non-blocking for backend-only deployments


async def main():
    logger.info("=" * 70)
    logger.info("  MedCare Pharma SCM Control Tower - Deployment Readiness Audit")
    logger.info("=" * 70)

    results = [
        check_python_version(),
        check_dependencies(),
        await check_database_connection(),
        await check_ml_model(),
        check_fastapi_app(),
        check_frontend_dist()
    ]

    logger.info("\n" + "=" * 70)
    if all(results):
        logger.info("  🎉 ALL CHECKS PASSED! Project is ready for production deployment.")
        logger.info("=" * 70)
        return 0
    else:
        logger.error("  ❌ SOME CHECKS FAILED. Please review the log above before deploying.")
        logger.info("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from backend.app.config import settings
from backend.app.database import engine, Base, AsyncSessionLocal, init_database
from backend.app.utils.data_seeder import seed_database
from backend.app.routers import (
    dashboard,
    inventory,
    transactions,
    demand,
    forecasts,
    replenishment,
    transfers,
    alerts,
    warehouses,
    scenarios,
    reports,
    settings as settings_router,
    notifications,
    metrics,
    assistant,
    ws,
    auth,
    users,
    suppliers
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MedCareControlTower")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown event handlers."""
    logger.info("Initializing MedCare SCM Control Tower database...")
    await init_database()
    
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    
    logger.info("MedCare SCM Control Tower backend started successfully.")
    yield
    logger.info("Shutting down MedCare SCM Control Tower backend...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Unified SCM Control Tower for MedCare Pharma (Cognizant NPN Hackathon E1 + P1)",
    lifespan=lifespan
)

# Configure CORS for Vite React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(inventory.router)
app.include_router(transactions.router)
app.include_router(demand.router)
app.include_router(forecasts.router)
app.include_router(replenishment.router)
app.include_router(transfers.router)
app.include_router(alerts.router)
app.include_router(warehouses.router)
app.include_router(scenarios.router)
app.include_router(reports.router)
app.include_router(settings_router.router)
app.include_router(notifications.router)
app.include_router(metrics.router)
app.include_router(assistant.router)
app.include_router(ws.router)
app.include_router(suppliers.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "HEALTHY",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "engines": {
            "inventory_engine": "ACTIVE",
            "demand_sensing_engine": "ACTIVE",
            "risk_engine": "ACTIVE",
            "expiry_fefo_engine": "ACTIVE",
            "network_balancing_engine": "ACTIVE",
            "replenishment_engine": "ACTIVE",
            "alert_escalation_engine": "ACTIVE",
            "scenario_simulation_engine": "ACTIVE"
        }
    }

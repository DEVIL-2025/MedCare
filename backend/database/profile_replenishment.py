import asyncio
import time
import sys
import io
from backend.app.database import AsyncSessionLocal
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.engines.demand_sensing_engine import DemandSensingEngine
import httpx
from httpx import ASGITransport
from backend.app.main import app

# Pylance-safe UTF-8 configuration
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")


async def profile_replenishment_pipeline():
    print("=================================================================")
    print("        PROFILING REPLENISHMENT DATA-LOADING PIPELINE")
    print("=================================================================")

    # 1. Profile via FastAPI HTTP endpoint (Cold Request)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        t0 = time.perf_counter()
        res = await client.get("/api/replenishment")
        t_cold = (time.perf_counter() - t0) * 1000
        print(f"[API Endpoint - Cold Start] GET /api/replenishment: {t_cold:.2f} ms (Status: {res.status_code})")

        # 2. Profile via FastAPI HTTP endpoint (Warm Request)
        t_warm_0 = time.perf_counter()
        res_warm = await client.get("/api/replenishment")
        t_warm = (time.perf_counter() - t_warm_0) * 1000
        print(f"[API Endpoint - Warm Query] GET /api/replenishment: {t_warm:.2f} ms (Status: {res_warm.status_code})")

    # 3. Detailed Component Profiling
    async with AsyncSessionLocal() as session:
        t1 = time.perf_counter()
        await NetworkBalancingEngine.identify_network_transfers(session)
        t_balancing = (time.perf_counter() - t1) * 1000
        print(f"  └─ NetworkBalancingEngine.identify_network_transfers: {t_balancing:.2f} ms")

        t2 = time.perf_counter()
        await ReplenishmentEngine.sync_recommendations(session)
        t_replenish = (time.perf_counter() - t2) * 1000
        print(f"  └─ ReplenishmentEngine.sync_recommendations: {t_replenish:.2f} ms")

        t3 = time.perf_counter()
        await DemandSensingEngine.compute_sku_warehouse_forecast(session, "P-1042", "MUM-01", 30)
        t_single_forecast = (time.perf_counter() - t3) * 1000
        print(f"  └─ Single SKU-DC Forecast Inference: {t_single_forecast:.2f} ms")


if __name__ == "__main__":
    asyncio.run(profile_replenishment_pipeline())

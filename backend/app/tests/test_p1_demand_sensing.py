import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.demand_sensing_engine import DemandSensingEngine


@pytest.mark.asyncio
async def test_demand_sensing_forecast_calculation():
    async with AsyncSessionLocal() as session:
        f_data = await DemandSensingEngine.compute_sku_warehouse_forecast(
            session=session,
            sku="P-1042",
            warehouse_id="BLR-01",
            horizon_days=30
        )
        assert "sensed_daily" in f_data
        assert "forecast_demand_next_30d" in f_data
        assert len(f_data["series"]) >= 30
        assert "summary" in f_data
        assert f_data["trend_direction"] in ["Increasing", "Stable", "Decreasing"]


@pytest.mark.asyncio
async def test_flu_season_demand_surge_detection():
    async with AsyncSessionLocal() as session:
        # P-1042 in PAT-01 has seasonal flu uplift
        f_data = await DemandSensingEngine.compute_sku_warehouse_forecast(
            session=session,
            sku="P-1042",
            warehouse_id="PAT-01",
            horizon_days=30
        )
        assert f_data["surge_detected"] is True
        assert f_data["surge_pct"] >= 25.0
        assert "Seasonality" in f_data["primary_driver"] or "Flu" in f_data["primary_driver"]

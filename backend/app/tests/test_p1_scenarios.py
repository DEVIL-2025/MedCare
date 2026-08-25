import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.scenario_simulation_engine import ScenarioSimulationEngine


@pytest.mark.asyncio
async def test_flu_season_scenario_simulation():
    async with AsyncSessionLocal() as session:
        result = await ScenarioSimulationEngine.run_simulation(
            session=session,
            name="Flu Season Peak (+60%)",
            demand_change_pct=60.0,
            lead_time_change_days=3,
            category_filter="Analgesics"
        )
        assert result["status"] == "Completed"
        assert result["impact_summary"]["projected_stockout_skus"] >= 1
        assert float(result["service_level"].replace("%", "")) < 95.0
        assert len(result["impact_trend"]) >= 8
        assert len(result["comparison"]) >= 5

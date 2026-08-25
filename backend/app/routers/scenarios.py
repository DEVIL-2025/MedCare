from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List

from backend.app.database import get_db
from backend.app.schemas.scenario import ScenarioRunRequest, ScenarioResponse
from backend.app.models.scenario import Scenario, ScenarioResult
from backend.app.engines.scenario_simulation_engine import ScenarioSimulationEngine

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])


@router.post("/run")
async def run_scenario(
    payload: ScenarioRunRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Runs a what-if supply chain simulation and returns impact analysis."""
    result = await ScenarioSimulationEngine.run_simulation(
        session=db,
        name=payload.name or "What-If Scenario",
        demand_change_pct=payload.get_demand_change(),
        lead_time_change_days=payload.get_lead_time_change(),
        starting_inventory_change_pct=payload.starting_inventory_change_pct,
        capacity_constraint_pct=payload.get_capacity_constraint(),
        distributor_demand_change_pct=payload.distributor_demand_change_pct,
        category_filter=payload.category_filter or "All Categories",
        warehouse_filter=payload.get_warehouse_filter()
    )
    return result


@router.get("/history")
async def get_scenario_history(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns past scenario simulation runs."""
    res = await db.execute(
        select(Scenario, ScenarioResult).join(
            ScenarioResult, Scenario.id == ScenarioResult.scenario_id
        ).order_by(Scenario.created_at.desc())
    )
    records = res.all()

    if not records:
        return []

    return [
        {
            "id": sc.id,
            "name": sc.name,
            "createdOn": sc.created_at.strftime("%d %b %Y, %I:%M %p"),
            "demandChange": f"+{int(sc.demand_change_pct)}%" if sc.demand_change_pct >= 0 else f"{int(sc.demand_change_pct)}%",
            "leadTimeChange": f"+{sc.lead_time_change_days} Days",
            "stockoutValue": res_item.stockout_value_formatted,
            "serviceLevel": f"{int(res_item.avg_service_level_pct)}%",
            "status": sc.status
        }
        for sc, res_item in records
    ]

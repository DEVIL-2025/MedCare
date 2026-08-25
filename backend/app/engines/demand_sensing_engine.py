from datetime import date, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.ml.predict import PredictionService
from backend.app.ml.model_registry import ModelRegistry
from backend.app.models.demand import DemandHistory, SeasonalEvent
from backend.app.models.forecast import DemandSurgeEvent


class DemandSensingEngine:
    """
    P1 Demand Sensing & Forecasting Engine.
    Powered by a trained Random Forest Regression model on actual time-series records from the database.
    """

    @staticmethod
    async def compute_sku_warehouse_forecast(
        session: AsyncSession,
        sku: str,
        warehouse_id: str,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Executes ML demand forecasting for the SKU-DC combination.
        """
        return await PredictionService.predict_demand(session, sku, warehouse_id, horizon_days)

    @staticmethod
    async def scan_and_record_demand_surges(session: AsyncSession) -> List[DemandSurgeEvent]:
        """
        Scans all SKUs and DCs to detect and record demand surges (>25% uplift) using ML predictions.
        """
        today = date(2026, 8, 24)
        skus_res = await session.execute(select(DemandHistory.sku, DemandHistory.warehouse_id).distinct())
        sku_dc_pairs = skus_res.all()

        surge_events = []
        for sku, wh_id in sku_dc_pairs:
            f_data = await PredictionService.predict_demand(session, sku, wh_id, 30)
            if f_data["surge_detected"]:
                surge = DemandSurgeEvent(
                    id=f"SURGE-{sku}-{wh_id}-{int(today.strftime('%Y%m%d'))}",
                    sku=sku,
                    warehouse_id=wh_id,
                    surge_pct=f_data["surge_pct"],
                    baseline_daily_demand=f_data["baseline_daily"],
                    sensed_daily_demand=f_data["sensed_daily"],
                    severity="CRITICAL" if f_data["surge_pct"] >= 50 else "HIGH",
                    primary_driver="Seasonal Flu Uplift (+60%)"
                )
                surge_events.append(surge)
                session.add(surge)

        return surge_events

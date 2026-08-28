import pandas as pd
import numpy as np
from typing import cast
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.demand import DemandHistory, SeasonalEvent
from backend.app.models.product import Product
from backend.app.config import settings


class DataPreparationService:
    @staticmethod
    async def extract_demand_dataset(session: AsyncSession) -> pd.DataFrame:
        """
        Fast SQL column extraction of time-series demand records.
        """
        q = select(
            DemandHistory.date,
            DemandHistory.sku,
            DemandHistory.warehouse_id,
            DemandHistory.actual_sales
        ).order_by(DemandHistory.sku, DemandHistory.warehouse_id, DemandHistory.date)
        
        res = await session.execute(q)
        rows = res.all()

        if not rows:
            return pd.DataFrame()

        df_demand = pd.DataFrame(rows, columns=["date", "sku", "warehouse_id", "actual_demand"])
        df_demand["date"] = pd.to_datetime(df_demand["date"])
        df_demand["actual_demand"] = df_demand["actual_demand"].fillna(0.0).astype(float)

        # Master maps
        prod_res = await session.execute(select(Product.sku, Product.category, Product.criticality, Product.unit_cost))
        prod_map = {r.sku: (r.category or "General", r.criticality or "Medium", float(r.unit_cost or 50.0)) for r in prod_res.all()}

        df_demand["category"] = df_demand["sku"].map(lambda s: prod_map[s][0] if s in prod_map else "General")
        df_demand["criticality"] = df_demand["sku"].map(lambda s: prod_map[s][1] if s in prod_map else "Medium")
        df_demand["unit_cost"] = df_demand["sku"].map(lambda s: prod_map[s][2] if s in prod_map else 50.0).astype(float)

        # Flu seasonal event window
        events_res = await session.execute(select(SeasonalEvent))
        events = events_res.scalars().all()

        uplift_series = np.zeros(len(df_demand), dtype=float)
        for ev in events:
            if not ev.start_date or not ev.end_date:
                continue
            ev_start = pd.to_datetime(cast(date, ev.start_date))
            ev_end = pd.to_datetime(cast(date, ev.end_date))
            ev_cats = [c.strip() for c in (ev.impacted_categories or "All").split(",")]
            
            mask = (df_demand["date"] >= ev_start) & (df_demand["date"] <= ev_end)
            if "All" not in ev_cats:
                mask = mask & df_demand["category"].isin(ev_cats)
            
            uplift_val = float(ev.expected_uplift_pct if ev.expected_uplift_pct is not None else settings.FLU_SEASON_UPLIFT_PCT)
            uplift_series[mask] = uplift_val / 100.0

        df_demand["seasonal_uplift_pct"] = uplift_series
        df_demand["distributor_orders_count"] = np.where(df_demand["seasonal_uplift_pct"] > 0, 5.0, 2.0)
        df_demand["is_promotional"] = np.where(df_demand["seasonal_uplift_pct"] > 0, 1.0, 0.0)

        return df_demand

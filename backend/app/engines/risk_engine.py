from datetime import timedelta, datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.models.inventory import Inventory
from backend.app.models.batch import Batch
from backend.app.models.warehouse import Warehouse
from backend.app.models.risk import InventoryRisk
from backend.app.engines.demand_sensing_engine import DemandSensingEngine
from backend.app.config import settings
from backend.app.utils.timezone import get_today_ist


class RiskEngine:
    """
    Evaluates multi-dimensional stockout and expiry risk for SKU-warehouse pairs.
    """

    @staticmethod
    async def evaluate_inventory_risk(
        session: AsyncSession,
        sku: str,
        warehouse_id: str
    ) -> Optional[InventoryRisk]:
        """
        Calculates Days of Cover, Stockout Risk Score, Estimated Stockout Date, and Expiry Risk.
        Returns None when no inventory record exists for the SKU and warehouse.
        """
        clean_sku = sku.strip().upper() if sku else ""
        clean_wh_id = warehouse_id.strip() if warehouse_id else ""
        today = get_today_ist()

        # 1. Fetch Inventory & Warehouse Metadata
        inv_res = await session.execute(
            select(Inventory).where(and_(Inventory.sku == clean_sku, Inventory.warehouse_id == clean_wh_id))
        )
        inv = inv_res.scalars().first()
        if not inv:
            return None

        wh_res = await session.execute(select(Warehouse).where(Warehouse.id == clean_wh_id))
        wh = wh_res.scalars().first()
        lead_time = wh.lead_time_days if (wh and wh.lead_time_days) else 5

        # 2. Get Sensed Daily Demand
        forecast_data = await DemandSensingEngine.compute_sku_warehouse_forecast(
            session, clean_sku, clean_wh_id, horizon_days=settings.FORECAST_HORIZON_DAYS
        )
        daily_sensed_demand = float(forecast_data["sensed_daily"]) if (forecast_data and "sensed_daily" in forecast_data) else 0.0

        # 3. Compute Days of Cover
        available_stock = float(inv.available_stock or 0.0)
        if daily_sensed_demand > 0:
            days_of_cover = round(available_stock / daily_sensed_demand, 1)
            inv.days_of_cover = days_of_cover
        else:
            days_of_cover = float("inf")
            inv.days_of_cover = 999.0

        # 4. Stockout Risk Level & Score (strictly bounded 0 to 100)
        lead_time_buffer = settings.LEAD_TIME_BUFFER_DAYS
        critical_cover_limit = lead_time
        high_cover_limit = lead_time + lead_time_buffer + 2
        inv_reorder_point = int(getattr(inv, "reorder_point", 0) or 0)
        inv_safety_stock = int(getattr(inv, "safety_stock", 0) or 0)

        if available_stock <= 0:
            stockout_level = "critical"
            stockout_score = 100.0
            estimated_stockout_date = today
        elif daily_sensed_demand <= 0:
            stockout_level = "low"
            stockout_score = 0.0
            estimated_stockout_date = None
        elif days_of_cover <= critical_cover_limit:
            stockout_level = "critical"
            stockout_score = min(100.0, max(85.0, 85.0 + (critical_cover_limit - days_of_cover) * 3.0))
            estimated_stockout_date = today + timedelta(days=max(1, int(days_of_cover)))
        elif days_of_cover <= high_cover_limit:
            stockout_level = "high"
            stockout_score = min(84.0, max(50.0, 65.0 + (high_cover_limit - days_of_cover) * 4.0))
            estimated_stockout_date = today + timedelta(days=int(days_of_cover))
        elif inv_reorder_point > 0 and days_of_cover <= (inv_reorder_point / daily_sensed_demand):
            stockout_level = "medium"
            stockout_score = 40.0
            estimated_stockout_date = today + timedelta(days=int(days_of_cover))
        else:
            stockout_level = "low"
            stockout_score = 15.0
            estimated_stockout_date = today + timedelta(days=int(days_of_cover))

        # 5. Expiry Risk Calculation across Batches
        batches_res = await session.execute(
            select(Batch).where(
                and_(
                    Batch.sku == clean_sku,
                    Batch.warehouse_id == clean_wh_id,
                    Batch.quantity > 0
                )
            )
        )
        batches = batches_res.scalars().all()

        near_expiry_units = 0
        critical_expiry_units = 0
        expired_units = 0
        for b in batches:
            if not b.expiry_date:
                continue
            days_to_exp = (b.expiry_date - today).days
            batch_qty = int(b.quantity or 0)
            if days_to_exp <= 0:
                expired_units += batch_qty
                b.status = "EXPIRED"
            elif days_to_exp <= settings.EXPIRY_CRITICAL_DAYS:
                critical_expiry_units += batch_qty
                b.status = "CRITICAL"
            elif days_to_exp <= settings.EXPIRY_AT_RISK_DAYS:
                near_expiry_units += batch_qty
                b.status = "NEAR_EXPIRY"

        if expired_units > 0 or critical_expiry_units > 0:
            expiry_level = "critical"
            expiry_score = 90.0
        elif near_expiry_units > 0:
            expiry_level = "high" if (available_stock > 0 and near_expiry_units > (available_stock * 0.3)) else "medium"
            expiry_score = 70.0 if expiry_level == "high" else 45.0
        else:
            expiry_level = "low"
            expiry_score = 10.0

        # Update Inventory overall risk
        inv.risk_level = stockout_level if stockout_score >= expiry_score else expiry_level

        # Summary text
        doc_str = f"{days_of_cover} days" if days_of_cover != float("inf") else "N/A"
        summary = (
            f"Stock covers {doc_str} vs {lead_time}d lead time. "
            f"Stockout risk: {stockout_level.upper()} ({int(stockout_score)}/100). "
            f"Near-expiry units: {near_expiry_units + critical_expiry_units}."
        )

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        risk_rec = InventoryRisk(
            sku=clean_sku,
            warehouse_id=clean_wh_id,
            current_inventory=int(inv.current_stock or 0),
            daily_sensed_demand=daily_sensed_demand,
            days_of_cover=days_of_cover if days_of_cover != float("inf") else 999.0,
            lead_time_days=lead_time,
            safety_stock=inv_safety_stock,
            stockout_risk_score=min(100.0, max(0.0, stockout_score)),
            stockout_risk_level=stockout_level,
            estimated_stockout_date=estimated_stockout_date,
            near_expiry_units=near_expiry_units + critical_expiry_units,
            expiry_risk_score=min(100.0, max(0.0, expiry_score)),
            expiry_risk_level=expiry_level,
            risk_summary=summary,
            calculated_at=now_utc
        )
        session.add(risk_rec)
        await session.flush()
        return risk_rec

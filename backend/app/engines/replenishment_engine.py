from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.replenishment import ReplenishmentRecommendation
from backend.app.models.transfer import InventoryTransfer
from backend.app.ml.predict import PredictionService
from backend.app.config import settings
from backend.app.utils.timezone import get_today_ist, get_now_ist


class ReplenishmentEngine:
    """
    P1 Dynamic Expiry-Aware Replenishment & Order Quantity Optimization Engine.
    Computes Recommended Order Quantities (ROQ), safety stock buffers,
    service-level targets, and order frequencies based on live ML forecasts and batch expiries.
    """

    @staticmethod
    async def sync_recommendations(
        session: AsyncSession,
        warehouse_id: Optional[str] = None,
        precomputed_forecasts: Optional[Dict[str, Any]] = None
    ) -> List[ReplenishmentRecommendation]:
        """
        High-performance bulk synchronization of replenishment recommendations.
        Eliminates N+1 queries by bulk pre-fetching references and vectorized ML forecasts.
        """
        today = get_today_ist()

        # 1. Bulk pre-fetch all necessary metadata (single queries instead of loops)
        query = (
            select(Inventory, Product)
            .join(Product, Inventory.sku == Product.sku)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(Product.is_active != False, Warehouse.is_active != False)
        )
        if warehouse_id and warehouse_id != "All":
            query = query.where(Inventory.warehouse_id == warehouse_id)

        inv_res = await session.execute(query)
        items = inv_res.all()

        wh_res = await session.execute(select(Warehouse).where(Warehouse.is_active != False))
        warehouses_map = {w.id: w for w in wh_res.scalars().all()}

        recs_res = await session.execute(select(ReplenishmentRecommendation))
        existing_recs_map = {f"{r.sku}_{r.warehouse_id}": r for r in recs_res.scalars().all()}

        trf_res = await session.execute(
            select(InventoryTransfer).where(InventoryTransfer.status == "RECOMMENDED")
        )
        matching_trf_map = {f"{t.sku}_{t.destination_warehouse_id}": t for t in trf_res.scalars().all()}

        # 2. Bulk get all forecasts in 1 ML pass
        all_forecasts = precomputed_forecasts if precomputed_forecasts is not None else await PredictionService.predict_all_demands(session, 30)

        active_recs = []

        for inv, prod in items:
            wh = warehouses_map.get(inv.warehouse_id)
            lead_time = wh.lead_time_days if wh else 5

            # Forecast lookup
            f_data = all_forecasts.get(f"{inv.sku}_{inv.warehouse_id}", {
                "sensed_daily": 50.0,
                "forecast_demand_next_30d": 1500,
                "surge_detected": False
            })
            daily_sensed = max(1.0, float(f_data.get("sensed_daily", 50.0)))
            forecast_30d = float(f_data.get("forecast_demand_next_30d", 1500))
            surge_detected = bool(f_data.get("surge_detected", False))

            # Required Stock Calculation
            lead_time_demand = daily_sensed * (lead_time + settings.LEAD_TIME_BUFFER_DAYS)
            target_stock = lead_time_demand + inv.safety_stock
            effective_inventory = inv.available_stock + inv.inbound_stock
            net_shortfall = target_stock - effective_inventory

            rec_key = f"{inv.sku}_{inv.warehouse_id}"
            existing_rec = existing_recs_map.get(rec_key)

            if net_shortfall <= 0 and inv.current_stock >= inv.reorder_point:
                if existing_rec is not None and existing_rec.status == "PENDING":
                    existing_rec.status = "RESOLVED"
                    existing_rec.reason_impact = f"Resolved: Stock restored to {inv.current_stock:,} units ({round(inv.current_stock / daily_sensed, 1)} days of cover)."
                continue

            raw_qty = max(net_shortfall, prod.moq)
            recommended_qty = int((raw_qty + 499) // 500 * 500)

            doc = inv.available_stock / daily_sensed
            if doc <= lead_time or inv.current_stock <= 0:
                priority = "critical"
                frequency = "Every 7 days (Surge Cadence)" if surge_detected else "Every 10 days"
                review_days = 7 if surge_detected else 10
                urgency = "URGENT_REPLENISHMENT"
            elif doc <= lead_time + 4:
                priority = "high"
                frequency = "Every 14 days"
                review_days = 14
                urgency = "REPLENISH"
            elif inv.current_stock < inv.reorder_point:
                priority = "medium"
                frequency = "Every 21 days"
                review_days = 21
                urgency = "REPLENISH"
            else:
                priority = "low"
                frequency = "Every 30 days"
                review_days = 30
                urgency = "MONITOR"

            matching_trf = matching_trf_map.get(rec_key)
            if matching_trf and settings.TRANSFER_FIRST_ENABLED:
                decision_type = "TRANSFER"
                preferred_source = matching_trf.source_warehouse_id
                cost_inr = round(recommended_qty * 3.0, 2)
                reason_what = f"Transfer {matching_trf.quantity:,} units of {prod.name} from {matching_trf.source_warehouse_id} to {inv.warehouse_id}"
                reason_why = (
                    f"{inv.warehouse_id} stock covers {round(doc, 1)} days vs {lead_time}d lead time. "
                    f"{matching_trf.source_warehouse_id} holds excess near-expiry inventory. "
                    f"Transfer avoids ₹{round(recommended_qty * prod.unit_cost, 2):,} in new procurement."
                )
                reason_when = "Dispatch transfer immediately (3-day inter-DC transit)."
                reason_impact = (
                    f"Eliminates stockout probability and utilizes near-expiry stock at {matching_trf.source_warehouse_id}."
                )
            else:
                decision_type = urgency
                preferred_source = "HealthGen Pharma" if prod.category in ["Analgesics", "Antibiotics"] else "MediSupplies Ltd."
                cost_inr = round(recommended_qty * prod.unit_cost, 2)
                reason_what = f"Procure {recommended_qty:,} units of {prod.name} from {preferred_source}"
                reason_why = (
                    f"Current stock ({inv.current_stock:,}) is below reorder threshold ({inv.reorder_point:,}). "
                    f"30-day sensed ML forecast is {int(forecast_30d):,} units."
                )
                reason_when = f"Issue Purchase Order within {24 if priority == 'critical' else 48} hours."
                reason_impact = f"Restores stock cover to {round((inv.current_stock + recommended_qty) / daily_sensed, 1)} days and maintains {int(settings.SERVICE_LEVEL * 100)}% service level."

            if existing_rec:
                existing_rec.current_stock = inv.current_stock
                existing_rec.forecast_demand_30d = forecast_30d
                existing_rec.safety_stock = inv.safety_stock
                existing_rec.recommended_quantity = recommended_qty
                existing_rec.recommended_frequency = frequency
                existing_rec.next_review_date = today + timedelta(days=review_days)
                existing_rec.decision_type = decision_type
                existing_rec.preferred_source = preferred_source
                existing_rec.estimated_cost_inr = cost_inr
                existing_rec.priority = priority
                existing_rec.reason_what = reason_what
                existing_rec.reason_why = reason_why
                existing_rec.reason_when = reason_when
                existing_rec.reason_impact = reason_impact
                if existing_rec.status not in ["APPROVED", "COMPLETED", "ACKNOWLEDGED", "REJECTED"]:
                    existing_rec.status = "PENDING"
                active_recs.append(existing_rec)
            else:
                rec_id = f"REC-{inv.sku}-{inv.warehouse_id}"
                new_rec = ReplenishmentRecommendation(
                    id=rec_id,
                    sku=inv.sku,
                    warehouse_id=inv.warehouse_id,
                    current_stock=inv.current_stock,
                    forecast_demand_30d=forecast_30d,
                    safety_stock=inv.safety_stock,
                    recommended_quantity=recommended_qty,
                    recommended_frequency=frequency,
                    next_review_date=today + timedelta(days=review_days),
                    decision_type=decision_type,
                    preferred_source=preferred_source,
                    estimated_cost_inr=cost_inr,
                    priority=priority,
                    reason_what=reason_what,
                    reason_why=reason_why,
                    reason_when=reason_when,
                    reason_impact=reason_impact,
                    status="PENDING",
                    requested_by="P1 Replenishment Optimizer",
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                session.add(new_rec)
                active_recs.append(new_rec)

        await session.flush()
        return active_recs

    @staticmethod
    async def compute_recommendations(session: AsyncSession) -> List[ReplenishmentRecommendation]:
        """Runs the replenishment optimization algorithm across all SKU-warehouse pairs."""
        return await ReplenishmentEngine.sync_recommendations(session)

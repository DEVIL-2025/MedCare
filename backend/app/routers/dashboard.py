from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from datetime import date, timedelta
from typing import Dict, Any, Optional, List

from backend.app.database import get_db
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.alert import Alert
from backend.app.models.replenishment import ReplenishmentRecommendation
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.demand import DemandHistory
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.ml.predict import PredictionService
from backend.app.utils.timezone import get_today_ist, get_now_ist, format_ist_datetime

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
async def get_dashboard_data(
    warehouse: Optional[str] = Query("All"),
    db: AsyncSession = Depends(get_db)
):
    """
    Dynamically computes aggregated KPIs, live demand vs inventory chart data,
    transfer recommendations, at-risk SKUs, warehouse health, and alert counts from the database.
    Supports network-wide aggregation ('All') and DC-specific filtering.
    """
    today = get_today_ist()

    # 0. Dynamically synchronize transfers, replenishment recommendations, and alerts with live DB state
    all_forecasts = await PredictionService.predict_all_demands(db, 30)
    await NetworkBalancingEngine.identify_network_transfers(db, precomputed_forecasts=all_forecasts)
    await ReplenishmentEngine.sync_recommendations(db, warehouse_id=warehouse, precomputed_forecasts=all_forecasts)
    await AlertEscalationEngine.sync_inventory_alerts(db, warehouse_id=warehouse)
    await db.commit()

    # 1. Total Inventory Units & Valuation from Database
    inv_query = (
        select(Inventory, Product)
        .join(Product, Inventory.sku == Product.sku)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .where(Product.is_active != False, Warehouse.is_active != False)
    )
    if warehouse and warehouse != "All":
        inv_query = inv_query.where(Inventory.warehouse_id == warehouse)

    inv_res = await db.execute(inv_query)
    inv_items = inv_res.all()

    # Dynamic status & risk evaluation ensuring direct DB changes reflect instantly
    for inv, prod in inv_items:
        dyn_status, dyn_risk = InventoryEngine.evaluate_inventory_status(
            inv.current_stock, inv.reorder_point, inv.safety_stock
        )
        inv.status = dyn_status
        inv.risk_level = dyn_risk

    total_units = sum(item[0].current_stock for item in inv_items)
    total_val_inr = sum(item[0].current_stock * item[1].unit_cost for item in inv_items)
    total_val_display = f"₹{total_val_inr / 10000000.0:.2f} Cr" if total_val_inr >= 10000000 else f"₹{total_val_inr / 100000.0:.2f} Lakhs"

    # 2. Critical & Low Stock SKUs
    critical_skus = len([i for i in inv_items if i[0].risk_level == "critical" or i[0].status in ["CRITICAL", "OUT_OF_STOCK"]])
    low_stock_skus = len([i for i in inv_items if i[0].status == "LOW_STOCK" or (i[0].risk_level == "high" and i[0].status not in ["CRITICAL", "OUT_OF_STOCK"])])
    stockout_risk_high = len([i for i in inv_items if i[0].risk_level in ["critical", "high"]])

    # 3. Replenishment Needed Value from DB
    rec_query = (
        select(ReplenishmentRecommendation)
        .join(Warehouse, ReplenishmentRecommendation.warehouse_id == Warehouse.id)
        .where(Warehouse.is_active != False, ReplenishmentRecommendation.status == "PENDING")
    )
    if warehouse and warehouse != "All":
        rec_query = rec_query.where(ReplenishmentRecommendation.warehouse_id == warehouse)
    recs_res = await db.execute(rec_query)
    recs = recs_res.scalars().all()
    replenish_val_inr = sum(r.estimated_cost_inr for r in recs)
    replenish_val_display = f"₹{replenish_val_inr / 10000000.0:.2f} Cr" if replenish_val_inr >= 10000000 else f"₹{replenish_val_inr / 100000.0:.2f} Lakhs"

    # 4. Inventory Health Percentage
    healthy_count = len([i for i in inv_items if i[0].status == "HEALTHY"])
    health_pct = round((healthy_count / max(1, len(inv_items))) * 100) if inv_items else 100

    # 5. Live Demand vs Inventory Outlook Chart (Past 4 weeks actuals + 4 weeks forward ML forecast + stock levels)
    # Determine the latest date present in DemandHistory to build a continuous 8-week timeline
    latest_dh_res = await db.execute(select(func.max(DemandHistory.date)))
    latest_date_db = latest_dh_res.scalar()
    anchor_date = latest_date_db if latest_date_db else today

    twenty_eight_days_ago = anchor_date - timedelta(days=28)
    dh_query = (
        select(DemandHistory.date, func.sum(DemandHistory.actual_sales).label("daily_sales"))
        .join(Warehouse, DemandHistory.warehouse_id == Warehouse.id)
        .where(Warehouse.is_active != False, DemandHistory.date > twenty_eight_days_ago, DemandHistory.date <= anchor_date)
    )
    if warehouse and warehouse != "All":
        dh_query = dh_query.where(DemandHistory.warehouse_id == warehouse)
    
    dh_query = dh_query.group_by(DemandHistory.date).order_by(DemandHistory.date.asc())
    dh_res = await db.execute(dh_query)
    hist_rows = {r[0]: r[1] for r in dh_res.all()}

    # Aggregate 4 strictly consecutive 7-day historical actuals
    demand_trend: List[Dict[str, Any]] = []
    current_active_stock = total_units
    avg_reorder_point = sum(i[0].reorder_point for i in inv_items) if inv_items else 5000

    past_week_sums = []
    for i in range(4, 0, -1):
        w_start = anchor_date - timedelta(days=i * 7)
        w_end = anchor_date - timedelta(days=(i - 1) * 7)
        w_sales = sum(
            sales for d, sales in hist_rows.items()
            if w_start < d <= w_end
        )
        past_week_sums.append(w_sales)
        w_label = f"Wk {5 - i} ({(w_start + timedelta(days=1)).strftime('%d %b')})"
        demand_trend.append({
            "date": w_label,
            "actual": w_sales,
            "forecast": None,
            "inventory": current_active_stock,
            "reorderPoint": int(avg_reorder_point)
        })

    # Forward 4 weeks continuous ML forecast projection starting immediately after anchor_date
    avg_weekly_demand = (sum(past_week_sums) / len(past_week_sums)) if past_week_sums and sum(past_week_sums) > 0 else 500
    running_projected_stock = current_active_stock

    for fw in range(1, 5):
        f_start = anchor_date + timedelta(days=(fw - 1) * 7 + 1)
        w_date = f"Wk +{fw} ({f_start.strftime('%d %b')})"
        w_forecast = round(avg_weekly_demand * (1.10 if fw <= 2 else 1.05))
        running_projected_stock = max(0, running_projected_stock - w_forecast)
        demand_trend.append({
            "date": w_date,
            "actual": None,
            "forecast": w_forecast,
            "inventory": running_projected_stock,
            "reorderPoint": int(avg_reorder_point)
        })

    # 6. Executive Recommendation Card (Highest priority validated action from DB)
    active_wh_subquery = select(Warehouse.id).where(Warehouse.is_active != False)
    trf_query = (
        select(InventoryTransfer, Product, Inventory)
        .join(Product, InventoryTransfer.sku == Product.sku)
        .join(
            Inventory,
            and_(
                Inventory.sku == InventoryTransfer.sku,
                Inventory.warehouse_id == InventoryTransfer.source_warehouse_id
            )
        )
        .where(
            Product.is_active != False,
            InventoryTransfer.source_warehouse_id.in_(active_wh_subquery),
            InventoryTransfer.destination_warehouse_id.in_(active_wh_subquery),
            InventoryTransfer.status == "RECOMMENDED"
        )
        .order_by(InventoryTransfer.estimated_savings_inr.desc())
    )
    if warehouse and warehouse != "All":
        trf_query = trf_query.where(
            or_(
                InventoryTransfer.source_warehouse_id == warehouse,
                InventoryTransfer.destination_warehouse_id == warehouse
            )
        )
    trf_res = await db.execute(trf_query)
    trf_candidates = trf_res.all()

    executive_recommendation = None
    stale_transfers_to_clean = []

    for primary_transfer, prod, src_inv in trf_candidates:
        avail_stock = src_inv.available_stock if src_inv.available_stock is not None else src_inv.current_stock
        min_transfer_threshold = min(50, prod.moq)

        # Check if source DC has sufficient stock to fulfill transfer
        if avail_stock < min_transfer_threshold:
            stale_transfers_to_clean.append(primary_transfer)
            continue

        # If available stock has dropped below original requested transfer quantity, dynamically scale down
        final_qty = primary_transfer.quantity
        if avail_stock < primary_transfer.quantity:
            scaled_qty = max(min_transfer_threshold, int(avail_stock // 50 * 50)) if avail_stock >= 50 else avail_stock
            if scaled_qty < min_transfer_threshold:
                stale_transfers_to_clean.append(primary_transfer)
                continue
            final_qty = scaled_qty
            primary_transfer.quantity = scaled_qty
            primary_transfer.available_at_source = avail_stock
            primary_transfer.estimated_savings_inr = round(scaled_qty * prod.unit_cost * 0.85, 2)
            primary_transfer.reason = f"FEFO Transfer: {scaled_qty:,} units from {primary_transfer.source_warehouse_id} to {primary_transfer.destination_warehouse_id} (scaled to live stock)."

        savings_str = f"₹{primary_transfer.estimated_savings_inr / 100000.0:.2f} Lakhs" if primary_transfer.estimated_savings_inr >= 100000 else f"₹{primary_transfer.estimated_savings_inr:,.0f}"
        executive_recommendation = {
            "id": primary_transfer.id,
            "action_type": "transfer",
            "transfer_id": primary_transfer.id,
            "recommendation_id": None,
            "what": f"Transfer {final_qty:,} units of {prod.name} from {primary_transfer.source_warehouse_id} to {primary_transfer.destination_warehouse_id}",
            "product": f"{prod.name} ({prod.sku})",
            "from": f"{primary_transfer.source_warehouse_id}",
            "to": f"{primary_transfer.destination_warehouse_id}",
            "why": primary_transfer.reason or f"Demand surge in {primary_transfer.destination_warehouse_id} creates imminent shortage, while {primary_transfer.source_warehouse_id} has excess near-expiry stock.",
            "expected_impact": "Prevents stockout, utilizes near-expiry stock, saves emergency purchase costs.",
            "savings": savings_str
        }
        break

    if stale_transfers_to_clean:
        for stale_trf in stale_transfers_to_clean:
            await db.delete(stale_trf)
        await db.commit()

    if not executive_recommendation:
        # Query top replenishment recommendation prioritized by urgency (critical > high > medium > low) and estimated cost
        priority_case = case(
            (ReplenishmentRecommendation.priority == "critical", 1),
            (ReplenishmentRecommendation.priority == "high", 2),
            (ReplenishmentRecommendation.priority == "medium", 3),
            (ReplenishmentRecommendation.priority == "low", 4),
            else_=5
        )
        rec_prio_query = (
            select(ReplenishmentRecommendation, Product)
            .join(Product, ReplenishmentRecommendation.sku == Product.sku)
            .join(Warehouse, ReplenishmentRecommendation.warehouse_id == Warehouse.id)
            .where(
                Warehouse.is_active != False,
                Product.is_active != False,
                ReplenishmentRecommendation.status == "PENDING"
            )
            .order_by(priority_case, ReplenishmentRecommendation.estimated_cost_inr.desc())
        )
        if warehouse and warehouse != "All":
            rec_prio_query = rec_prio_query.where(ReplenishmentRecommendation.warehouse_id == warehouse)
        
        rec_prio_res = await db.execute(rec_prio_query)
        rec_item = rec_prio_res.first()

        if rec_item:
            first_rec, prod = rec_item
            cost_str = f"₹{first_rec.estimated_cost_inr / 100000.0:.2f} Lakhs" if first_rec.estimated_cost_inr >= 100000 else f"₹{first_rec.estimated_cost_inr:,.0f}"
            executive_recommendation = {
                "id": first_rec.id,
                "action_type": "replenishment",
                "transfer_id": None,
                "recommendation_id": first_rec.id,
                "what": f"Replenish {first_rec.recommended_quantity:,} units of {prod.name} for {first_rec.warehouse_id}",
                "product": f"{prod.name} ({first_rec.sku})",
                "from": first_rec.preferred_source or "HealthGen Pharma",
                "to": first_rec.warehouse_id,
                "why": first_rec.reason_why or "Stock level below dynamic safety stock threshold.",
                "expected_impact": first_rec.reason_impact or "Restores safe days of cover.",
                "savings": cost_str
            }

    # 7. Top At-Risk SKUs from DB
    at_risk_list = []
    for inv, prod in inv_items:
        if inv.risk_level in ["critical", "high"] or inv.status in ["CRITICAL", "OUT_OF_STOCK", "LOW_STOCK"]:
            at_risk_list.append({
                "sku": prod.sku,
                "name": prod.name,
                "category": prod.category,
                "warehouse": inv.warehouse_id,
                "currentStock": inv.current_stock,
                "reorderPoint": inv.reorder_point,
                "safetyStock": inv.safety_stock,
                "daysOfCover": round(inv.days_of_cover, 1) if inv.days_of_cover is not None else 0.0,
                "risk": inv.risk_level or "high",
                "status": inv.status.replace("_", " ").title()
            })
    at_risk_list.sort(key=lambda x: x["daysOfCover"])

    # 8. Warehouse Health from DB
    wh_res = await db.execute(select(Warehouse).where(Warehouse.is_active != False).order_by(Warehouse.id.asc()))
    warehouses = wh_res.scalars().all()

    # Precalculate per-warehouse inventory sum for active warehouses
    all_inv_res = await db.execute(
        select(Inventory.warehouse_id, func.sum(Inventory.current_stock))
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .where(Warehouse.is_active != False)
        .group_by(Inventory.warehouse_id)
    )
    wh_inv_map = {row[0]: row[1] for row in all_inv_res.all()}

    warehouse_health = [
        {
            "id": w.id,
            "name": w.name,
            "inventory": f"{wh_inv_map.get(w.id, 0):,} units",
            "status": w.status
        }
        for w in warehouses
    ]
    if warehouse and warehouse != "All":
        warehouse_health = [w for w in warehouse_health if w["id"] == warehouse]

    # 9. Alert Summary Counts from DB (Active Warehouses Only)
    alert_query = (
        select(Alert)
        .join(Warehouse, Alert.warehouse_id == Warehouse.id)
        .where(Warehouse.is_active != False)
    )
    if warehouse and warehouse != "All":
        alert_query = alert_query.where(Alert.warehouse_id == warehouse)
    alerts_res = await db.execute(alert_query)
    all_alerts = alerts_res.scalars().all()

    alert_summary = {
        "total": len([a for a in all_alerts if a.status != "Resolved"]),
        "critical": len([a for a in all_alerts if a.severity == "critical" and a.status != "Resolved"]),
        "warning": len([a for a in all_alerts if a.severity == "warning" and a.status != "Resolved"]),
        "medium": len([a for a in all_alerts if a.severity == "medium" and a.status != "Resolved"]),
        "good": len([a for a in all_alerts if a.status == "Resolved"])
    }

    return {
        "kpis": {
            "total_inventory_value": total_val_display,
            "total_inventory_value_raw": total_val_inr,
            "total_inventory_units": f"{total_units:,}",
            "critical_skus": critical_skus,
            "low_stock_skus": low_stock_skus,
            "replenishment_needed": f"{len(recs)} SKUs ({replenish_val_display})",
            "stockout_risk_high": stockout_risk_high,
            "inventory_health": f"{health_pct}%",
        },
        "demand_trend": demand_trend,
        "executive_recommendation": executive_recommendation,
        "top_at_risk_skus": at_risk_list[:8],
        "warehouse_health": warehouse_health[:6],
        "alert_summary": alert_summary,
        "scope": warehouse,
        "server_time": get_now_ist().isoformat(),
        "formatted_server_time": format_ist_datetime(get_now_ist())
    }

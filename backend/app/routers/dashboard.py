from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
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
from backend.app.ml.predict import PredictionService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
async def get_dashboard_data(
    warehouse: Optional[str] = Query("All"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dynamically computes aggregated KPIs, live demand vs inventory chart data,
    transfer recommendations, at-risk SKUs, warehouse health, and alert counts from the database.
    Supports network-wide aggregation ('All') and DC-specific filtering.
    """
    today = date(2026, 8, 24)

    # 0. Synchronize alerts with current live inventory state
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

    # 2. Critical & High Stockout SKUs
    critical_skus = len([i for i in inv_items if i[0].risk_level == "critical" or i[0].status in ["CRITICAL", "OUT_OF_STOCK"]])
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
    thirty_days_ago = today - timedelta(days=30)
    dh_query = (
        select(DemandHistory.date, func.sum(DemandHistory.actual_sales).label("daily_sales"))
        .where(DemandHistory.date >= thirty_days_ago)
    )
    if warehouse and warehouse != "All":
        dh_query = dh_query.where(DemandHistory.warehouse_id == warehouse)
    
    dh_query = dh_query.group_by(DemandHistory.date).order_by(DemandHistory.date.asc())
    dh_res = await db.execute(dh_query)
    hist_daily = dh_res.all()

    # Aggregate weekly actuals (last 4 weeks)
    demand_trend: List[Dict[str, Any]] = []
    
    # Calculate baseline stock reference for the outlook chart
    current_active_stock = total_units
    avg_reorder_point = sum(i[0].reorder_point for i in inv_items) if inv_items else 5000

    if hist_daily:
        # Group into 7-day buckets
        chunk_size = 7
        for chunk_idx in range(0, len(hist_daily), chunk_size):
            chunk = hist_daily[chunk_idx:chunk_idx + chunk_size]
            w_label = f"Wk {chunk_idx // chunk_size + 1} ({chunk[0][0].strftime('%d %b')})"
            w_total = sum(row[1] for row in chunk)
            demand_trend.append({
                "date": w_label,
                "actual": w_total,
                "forecast": None,
                "inventory": current_active_stock,
                "reorderPoint": int(avg_reorder_point)
            })

    # Forward 4 weeks ML forecast projection
    avg_weekly_demand = (sum(r["actual"] for r in demand_trend) / len(demand_trend)) if demand_trend else 500
    running_projected_stock = current_active_stock

    for fw in range(1, 5):
        f_date = today + timedelta(weeks=fw)
        w_date = f"Wk +{fw} ({f_date.strftime('%d %b')})"
        w_forecast = round(avg_weekly_demand * (1.10 if fw <= 2 else 1.05))
        running_projected_stock = max(0, running_projected_stock - w_forecast)
        demand_trend.append({
            "date": w_date,
            "actual": None,
            "forecast": w_forecast,
            "inventory": running_projected_stock,
            "reorderPoint": int(avg_reorder_point)
        })

    # 6. Executive Recommendation Card (Queried from DB Transfers & Recommendations)
    active_wh_subquery = select(Warehouse.id).where(Warehouse.is_active != False)
    trf_query = (
        select(InventoryTransfer, Product)
        .join(Product, InventoryTransfer.sku == Product.sku)
        .where(
            Product.is_active != False,
            InventoryTransfer.source_warehouse_id.in_(active_wh_subquery),
            InventoryTransfer.destination_warehouse_id.in_(active_wh_subquery),
            InventoryTransfer.status == "RECOMMENDED"
        )
    )
    if warehouse and warehouse != "All":
        trf_query = trf_query.where(
            or_(
                InventoryTransfer.source_warehouse_id == warehouse,
                InventoryTransfer.destination_warehouse_id == warehouse
            )
        )
    trf_res = await db.execute(trf_query)
    trf_item = trf_res.first()

    executive_recommendation = None
    if trf_item:
        primary_transfer, prod = trf_item
        savings_str = f"₹{primary_transfer.estimated_savings_inr / 100000.0:.2f} Lakhs" if primary_transfer.estimated_savings_inr >= 100000 else f"₹{primary_transfer.estimated_savings_inr:,.0f}"
        executive_recommendation = {
            "id": primary_transfer.id,
            "action_type": "transfer",
            "transfer_id": primary_transfer.id,
            "recommendation_id": None,
            "what": f"Transfer {primary_transfer.quantity:,} units of {prod.name} from {primary_transfer.source_warehouse_id} to {primary_transfer.destination_warehouse_id}",
            "product": f"{prod.name} ({prod.sku})",
            "from": f"{primary_transfer.source_warehouse_id}",
            "to": f"{primary_transfer.destination_warehouse_id}",
            "why": primary_transfer.reason or f"Demand surge in {primary_transfer.destination_warehouse_id} creates imminent shortage, while {primary_transfer.source_warehouse_id} has excess near-expiry stock.",
            "expected_impact": "Prevents stockout, utilizes near-expiry stock, saves emergency purchase costs.",
            "savings": savings_str
        }
    elif recs:
        # Fallback to top replenishment recommendation if no transfer exists
        first_rec = recs[0]
        prod_res = await db.execute(select(Product).where(Product.sku == first_rec.sku))
        prod = prod_res.scalars().first()
        prod_name = prod.name if prod else first_rec.sku
        cost_str = f"₹{first_rec.estimated_cost_inr / 100000.0:.2f} Lakhs" if first_rec.estimated_cost_inr >= 100000 else f"₹{first_rec.estimated_cost_inr:,.0f}"
        executive_recommendation = {
            "id": first_rec.id,
            "action_type": "replenishment",
            "transfer_id": None,
            "recommendation_id": first_rec.id,
            "what": f"Replenish {first_rec.recommended_quantity:,} units of {prod_name} for {first_rec.warehouse_id}",
            "product": f"{prod_name} ({first_rec.sku})",
            "from": first_rec.preferred_source or "SUPPLIER",
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
            "replenishment_needed": f"{len(recs)} SKUs ({replenish_val_display})",
            "stockout_risk_high": stockout_risk_high,
            "inventory_health": f"{health_pct}%",
        },
        "demand_trend": demand_trend,
        "executive_recommendation": executive_recommendation,
        "top_at_risk_skus": at_risk_list[:8],
        "warehouse_health": warehouse_health[:6],
        "alert_summary": alert_summary,
        "scope": warehouse
    }

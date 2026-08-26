import re
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from backend.app.database import get_db
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.models.replenishment import ReplenishmentRecommendation, PurchaseOrder
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.alert import Alert
from backend.app.models.transaction import InventoryTransaction
from backend.app.models.demand import DemandHistory, SeasonalEvent
from backend.app.models.forecast import ForecastRecord, DemandSurgeEvent
from backend.app.ml.predict import PredictionService
from backend.app.services.gemini_service import gemini_service
from backend.app.utils.timezone import get_today_ist

router = APIRouter(prefix="/api/assistant", tags=["AI Assistant"])


class ChatRequest(BaseModel):
    query: str
    warehouse: Optional[str] = None


class ChatResponse(BaseModel):
    query: str
    answer: str
    category: str
    confidence: float
    data: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None


@router.post("/chat", response_model=ChatResponse)
async def assistant_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    """
    Grounded AI Supply Chain Assistant.
    Analyzes user queries, queries exact real-time PostgreSQL database state,
    and rephrases verified data into natural language using Gemini 2.0 Flash.
    Covers inventory, SKU stock, warehouses, replenishment, FEFO, alerts, transactions, and consumption.
    """
    query_text = req.query.strip().lower()
    today = get_today_ist()

    # 1. Pre-load active master catalogs
    prods_res = await db.execute(select(Product).where(Product.is_active != False))
    products = prods_res.scalars().all()
    products_by_sku = {p.sku.upper(): p for p in products}
    products_by_name = {p.name.lower(): p for p in products}

    wh_res = await db.execute(select(Warehouse).where(Warehouse.is_active != False))
    warehouses = wh_res.scalars().all()
    wh_map = {w.id.upper(): w for w in warehouses}

    # Extract detected SKU or Warehouse in query with smart token matching
    detected_sku = None
    for sku, p in products_by_sku.items():
        if sku.lower() in query_text:
            detected_sku = sku
            break
        p_clean = re.sub(r'[^a-zA-Z0-9\s]', '', p.name).lower()
        if p_clean in query_text:
            detected_sku = sku
            break
        # Match significant product name terms (e.g. 'paracetamol', 'amoxicillin', 'insulin', 'azithromycin')
        tokens = [t for t in p_clean.split() if len(t) >= 4 and t not in ['units', 'syrup', 'inhaler', 'validation', 'tablets']]
        if any(t in query_text for t in tokens):
            detected_sku = sku
            break

    detected_wh = None
    for wh_id, w in wh_map.items():
        if wh_id.lower() in query_text:
            detected_wh = wh_id
            break
        w_clean = re.sub(r'[^a-zA-Z0-9\s]', '', w.name).lower()
        loc_clean = re.sub(r'[^a-zA-Z0-9\s]', '', w.location).lower()
        if w_clean in query_text or loc_clean in query_text:
            detected_wh = wh_id
            break
        wh_tokens = [t for t in (w_clean + " " + loc_clean).split() if len(t) >= 4 and t not in ['regional', 'warehouse', 'distribution', 'center']]
        if any(t in query_text for t in wh_tokens):
            detected_wh = wh_id
            break

    answer: str = ""
    category: str = "General"
    confidence: float = 0.85
    data: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None

    # ==========================================
    # INTENT 1: INVENTORY & STOCK LEVEL QUERY
    # ==========================================
    if any(w in query_text for w in ["stock", "inventory", "units", "available", "quantity", "how many", "count"]):
        category = "Inventory"
        if detected_sku:
            prod = products_by_sku[detected_sku]
            inv_query = (
                select(Inventory)
                .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
                .where(Warehouse.is_active != False, Inventory.sku == detected_sku)
            )
            if detected_wh:
                inv_query = inv_query.where(Inventory.warehouse_id == detected_wh)
            inv_res = await db.execute(inv_query)
            inv_list = inv_res.scalars().all()

            if not inv_list:
                confidence = 0.98
                answer = f"No active inventory records found in PostgreSQL for **{prod.name} ({detected_sku})** in the specified warehouse scope."
                data = {"sku": detected_sku, "product": prod.name, "records_found": 0}
                suggested_actions = ["View all inventory", "Check other distribution centers"]
            else:
                total_st = sum(i.current_stock for i in inv_list)
                total_avail = sum(i.available_stock for i in inv_list)
                breakdowns = [
                    f"• **{i.warehouse_id}**: {i.current_stock:,} units ({i.status.replace('_', ' ').title()})"
                    for i in inv_list
                ]
                breakdown_dicts = [
                    {
                        "warehouse_id": i.warehouse_id,
                        "current_stock": i.current_stock,
                        "available_stock": i.available_stock,
                        "status": i.status,
                        "reorder_point": i.reorder_point,
                        "safety_stock": i.safety_stock,
                        "days_of_cover": i.days_of_cover
                    }
                    for i in inv_list
                ]

                confidence = 0.99
                answer = (
                    f"📊 **Inventory Status for {prod.name} ({detected_sku})**:\n"
                    f"- **Total Physical Stock**: {total_st:,} units\n"
                    f"- **Available for Dispensing**: {total_avail:,} units\n"
                    f"- **Unit Cost**: ₹{prod.unit_cost}\n\n"
                    f"**Regional DC Breakdown**:\n" + "\n".join(breakdowns)
                )
                data = {
                    "sku": detected_sku,
                    "product_name": prod.name,
                    "category": prod.category,
                    "unit_cost_inr": prod.unit_cost,
                    "total_stock": total_st,
                    "total_available_stock": total_avail,
                    "warehouse_breakdown": breakdown_dicts
                }
                suggested_actions = [f"View {prod.name} in Inventory", f"Check {detected_sku} batches"]
        else:
            # General inventory overview
            total_inv_res = await db.execute(
                select(func.sum(Inventory.current_stock), func.count(Inventory.id)).join(
                    Warehouse, Inventory.warehouse_id == Warehouse.id
                ).where(Warehouse.is_active != False)
            )
            t_units, t_count = total_inv_res.one()
            t_units = t_units or 0

            confidence = 0.95
            answer = (
                f"📦 **Network Inventory Overview**:\n"
                f"- Total active items across network: **{t_count} SKU-DC pairs**\n"
                f"- Total physical stock in active warehouses: **{t_units:,} units**\n"
                f"- Active Distribution Centers: **{len(warehouses)} nodes** ({', '.join(wh_map.keys())})"
            )
            data = {
                "total_units": t_units,
                "active_items_count": t_count,
                "active_dcs": len(warehouses),
                "distribution_centers": list(wh_map.keys())
            }
            suggested_actions = ["View Inventory Dashboard", "Check Low Stock Items"]

    # ==========================================
    # INTENT 2: FEFO & EXPIRY RISK QUERY
    # ==========================================
    elif any(w in query_text for w in ["fefo", "expiry", "expire", "expiring", "near expiry", "batch", "shelf life"]):
        category = "FEFO & Expiry"
        b_query = select(Batch, Product).join(Product, Batch.sku == Product.sku).join(
            Warehouse, Batch.warehouse_id == Warehouse.id
        ).where(Warehouse.is_active != False, Batch.quantity > 0, Batch.expiry_date > today)

        if detected_sku:
            b_query = b_query.where(Batch.sku == detected_sku)
        if detected_wh:
            b_query = b_query.where(Batch.warehouse_id == detected_wh)

        b_query = b_query.order_by(Batch.expiry_date.asc())
        b_res = await db.execute(b_query)
        batches = b_res.all()

        if not batches:
            confidence = 0.95
            answer = "✅ No active near-expiry batches detected in PostgreSQL for the requested scope."
            data = {"batches_found": 0}
            suggested_actions = ["View Expiry Report", "Review Batches"]
        else:
            batch_lines = []
            batch_data_list = []
            for idx, (b, p) in enumerate(batches[:6], 1):
                days_left = (b.expiry_date - today).days
                batch_lines.append(
                    f"{idx}. **Batch {b.id}** ({p.name} @ {b.warehouse_id}): {b.quantity:,} units | Expiry: {b.expiry_date} ({days_left}d left)"
                )
                batch_data_list.append({
                    "batch_id": b.id,
                    "sku": b.sku,
                    "product_name": p.name,
                    "warehouse_id": b.warehouse_id,
                    "quantity": b.quantity,
                    "expiry_date": str(b.expiry_date),
                    "days_until_expiry": days_left
                })

            confidence = 0.98
            answer = (
                f"⏳ **FEFO Batch Dispatch Priority (Earliest Expiry First)**:\n"
                f"Active valid batches sorted strictly by expiration date:\n\n" +
                "\n".join(batch_lines) +
                "\n\n*Note: Expired batches and zero-quantity records are automatically excluded.*"
            )
            data = {"total_near_expiry_batches": len(batches), "batches": batch_data_list}
            suggested_actions = ["Open Transfers & FEFO Balancing Tab", "Check Batch Expiry Report"]

    # ==========================================
    # INTENT 3: REPLENISHMENT & TRANSFERS QUERY
    # ==========================================
    elif any(w in query_text for w in ["replenish", "replenishment", "order", "purchase order", "po", "transfer", "reorder", "procure"]):
        category = "Replenishment"
        rec_query = select(ReplenishmentRecommendation, Product).join(
            Product, ReplenishmentRecommendation.sku == Product.sku
        ).join(Warehouse, ReplenishmentRecommendation.warehouse_id == Warehouse.id).where(
            Warehouse.is_active != False,
            ReplenishmentRecommendation.status == "PENDING"
        )
        if detected_wh:
            rec_query = rec_query.where(ReplenishmentRecommendation.warehouse_id == detected_wh)
        if detected_sku:
            rec_query = rec_query.where(ReplenishmentRecommendation.sku == detected_sku)

        recs_res = await db.execute(rec_query)
        recs = recs_res.all()

        trf_query = select(InventoryTransfer, Product).join(Product, InventoryTransfer.sku == Product.sku).where(
            InventoryTransfer.status == "RECOMMENDED"
        )
        trf_res = await db.execute(trf_query)
        transfers = trf_res.all()

        rec_lines = []
        rec_data_list = []
        for r, p in recs[:5]:
            rec_lines.append(
                f"• **{p.name} ({r.sku}) @ {r.warehouse_id}**: Order **{r.recommended_quantity:,} units** via {r.decision_type} (Est: ₹{r.estimated_cost_inr/100000:.1f} L) — Priority: {r.priority.upper()}"
            )
            rec_data_list.append({
                "sku": r.sku,
                "product_name": p.name,
                "warehouse_id": r.warehouse_id,
                "recommended_quantity": r.recommended_quantity,
                "decision_type": r.decision_type,
                "estimated_cost_inr": r.estimated_cost_inr,
                "priority": r.priority
            })

        trf_lines = [
            f"• **{p.name}**: Transfer {t.quantity:,} units from {t.source_warehouse_id} ➔ {t.destination_warehouse_id} (Avoids ₹{t.estimated_savings_inr:,.0f} new procurement)"
            for t, p in transfers[:3]
        ]
        trf_data_list = [
            {
                "sku": t.sku,
                "product_name": p.name,
                "source_warehouse_id": t.source_warehouse_id,
                "destination_warehouse_id": t.destination_warehouse_id,
                "quantity": t.quantity,
                "estimated_savings_inr": t.estimated_savings_inr,
                "reason": t.reason
            }
            for t, p in transfers[:5]
        ]

        ans = f"🚚 **Active Replenishment Recommendations** ({len(recs)} pending):\n\n"
        if rec_lines:
            ans += "\n".join(rec_lines) + "\n\n"
        else:
            ans += "All inventory levels in scope are above reorder thresholds.\n\n"

        if trf_lines:
            ans += f"🔄 **Inter-DC FEFO Balancing Transfers**:\n" + "\n".join(trf_lines)

        confidence = 0.98
        answer = ans
        data = {
            "pending_recommendations_count": len(recs),
            "recommendations": rec_data_list,
            "active_transfers_count": len(transfers),
            "transfers": trf_data_list
        }
        suggested_actions = ["Review Replenishment Recommendations", "Approve 1-Click POs"]

    # ==========================================
    # INTENT 4: ALERTS & SHORTAGE RISKS
    # ==========================================
    elif any(w in query_text for w in ["alert", "alerts", "critical", "warning", "risk", "stockout", "shortage", "escalation"]):
        category = "Alerts"
        al_query = select(Alert).join(Warehouse, Alert.warehouse_id == Warehouse.id).where(
            Warehouse.is_active != False,
            Alert.status != "Resolved"
        )
        if detected_wh:
            al_query = al_query.where(Alert.warehouse_id == detected_wh)
        if detected_sku:
            al_query = al_query.where(Alert.sku == detected_sku)

        al_query = al_query.order_by(Alert.severity.desc(), Alert.created_at.desc())
        al_res = await db.execute(al_query)
        active_alerts = al_res.scalars().all()

        if not active_alerts:
            confidence = 0.97
            answer = "🎉 **Zero Active Alerts**: All distribution centers are operating within safe inventory and expiry thresholds."
            data = {"active_alerts": 0}
            suggested_actions = ["View Alerts Dashboard"]
        else:
            alert_lines = [
                f"• **[{a.severity.upper()}] {a.alert_type}** ({a.sku or 'Network'} @ {a.warehouse_id}): {a.detail} (Status: {a.status})"
                for a in active_alerts[:5]
            ]
            alert_data_list = [
                {
                    "alert_id": a.id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "sku": a.sku,
                    "warehouse_id": a.warehouse_id,
                    "detail": a.detail,
                    "status": a.status
                }
                for a in active_alerts[:10]
            ]

            confidence = 0.99
            answer = (
                f"🚨 **Active Supply Chain Alerts** ({len(active_alerts)} unresolved):\n\n" +
                "\n".join(alert_lines)
            )
            data = {"total_active_alerts": len(active_alerts), "alerts": alert_data_list}
            suggested_actions = ["View Alerts Dashboard", "Acknowledge Critical Alerts"]

    # ==========================================
    # INTENT 5: TRANSACTIONS & INTERNAL CONSUMPTION
    # ==========================================
    elif any(w in query_text for w in ["transaction", "transactions", "sale", "receipt", "consumption", "dispensing", "audit log", "movement"]):
        category = "Transactions"
        tx_query = select(InventoryTransaction).join(
            Warehouse, InventoryTransaction.warehouse_id == Warehouse.id
        ).where(Warehouse.is_active != False)

        if "consumption" in query_text:
            tx_query = tx_query.where(InventoryTransaction.transaction_type == "CONSUMPTION")
        elif "sale" in query_text:
            tx_query = tx_query.where(InventoryTransaction.transaction_type == "SALE")
        elif "receipt" in query_text:
            tx_query = tx_query.where(InventoryTransaction.transaction_type == "RECEIPT")

        if detected_wh:
            tx_query = tx_query.where(InventoryTransaction.warehouse_id == detected_wh)
        if detected_sku:
            tx_query = tx_query.where(InventoryTransaction.sku == detected_sku)

        tx_query = tx_query.order_by(InventoryTransaction.timestamp.desc())
        tx_res = await db.execute(tx_query)
        txs = tx_res.scalars().all()

        if not txs:
            confidence = 0.96
            answer = "📋 No inventory transactions matching the specified criteria were found in PostgreSQL ledger."
            data = {"transactions_found": 0}
            suggested_actions = ["Record Stock Transaction", "View Audit Ledger"]
        else:
            tx_lines = []
            tx_data_list = []
            for t in txs[:6]:
                p_obj = products_by_sku.get(t.sku)
                p_name = p_obj.name if p_obj else t.sku
                tx_lines.append(
                    f"• **[{t.transaction_type}] {p_name} @ {t.warehouse_id}**: {t.quantity:+,} units ({t.previous_stock} ➔ {t.new_stock}) | {t.reason or 'Standard movement'} ({t.timestamp.strftime('%d %b %H:%M')})"
                )
                tx_data_list.append({
                    "transaction_id": t.id,
                    "type": t.transaction_type,
                    "sku": t.sku,
                    "product_name": p_name,
                    "warehouse_id": t.warehouse_id,
                    "quantity": t.quantity,
                    "previous_stock": t.previous_stock,
                    "new_stock": t.new_stock,
                    "reason": t.reason,
                    "timestamp": t.timestamp.isoformat()
                })

            confidence = 0.98
            answer = (
                f"📝 **Recent Inventory Transactions & Consumption Ledger** ({len(txs)} records):\n\n" +
                "\n".join(tx_lines)
            )
            data = {"total_transactions": len(txs), "recent_transactions": tx_data_list}
            suggested_actions = ["Open Inventory Audit Ledger", "Record Stock Transaction"]

    # ==========================================
    # INTENT 7: DEMAND FORECAST
    # ==========================================
    elif any(w in query_text for w in ["forecast", "predict", "prediction", "demand", "ml model", "future demand", "projected"]):
        category = "Demand Forecast"
        fc_query = (
            select(ForecastRecord, Product)
            .join(Product, ForecastRecord.sku == Product.sku)
            .join(Warehouse, ForecastRecord.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False)
        )
        if detected_sku:
            fc_query = fc_query.where(ForecastRecord.sku == detected_sku)
        if detected_wh:
            fc_query = fc_query.where(ForecastRecord.warehouse_id == detected_wh)

        fc_query = fc_query.order_by(ForecastRecord.forecast_date.asc())
        fc_res = await db.execute(fc_query)
        records = fc_res.all()

        if not records:
            # Check if live ML prediction engine can supply demand forecast for detected SKU/WH
            ml_data = None
            if detected_sku:
                try:
                    wh_target = detected_wh or "BLR-01"
                    ml_data = await PredictionService.predict_demand(db, detected_sku, wh_target, 30)
                except Exception:
                    ml_data = None

            if ml_data and ml_data.get("forecast_demand_next_30d"):
                prod = products_by_sku[detected_sku]
                wh_target = detected_wh or "BLR-01"
                total_30d = ml_data.get("forecast_demand_next_30d", 0)
                sensed_daily = ml_data.get("sensed_daily", 0.0)
                confidence_pct = ml_data.get("confidence_level_pct", 87.4)
                trend = ml_data.get("trend_direction", "Stable")
                driver = ml_data.get("primary_driver", "Baseline Dispensing Velocity")
                peak_date = ml_data.get("predicted_peak_date", "")
                peak_units = ml_data.get("predicted_peak_units", 0)

                confidence = 0.98
                answer = (
                    f"📈 **ML Demand Forecast for {prod.name} ({detected_sku}) @ {wh_target}**:\n"
                    f"- **30-Day Projected Demand**: {total_30d:,} units\n"
                    f"- **Sensed Daily Rate**: {sensed_daily:.1f} units/day\n"
                    f"- **Predicted Peak**: {peak_units:,} units ({peak_date})\n"
                    f"- **Model Confidence**: {confidence_pct}%\n"
                    f"- **Trend Direction**: {trend}\n"
                    f"- **Primary Driver**: {driver}"
                )
                data = {
                    "sku": detected_sku,
                    "product_name": prod.name,
                    "warehouse_id": wh_target,
                    "forecast_horizon_days": 30,
                    "forecast_demand_next_30d": total_30d,
                    "sensed_daily_rate": sensed_daily,
                    "predicted_peak_units": peak_units,
                    "confidence_pct": confidence_pct,
                    "trend_direction": trend,
                    "primary_driver": driver
                }
                suggested_actions = [
                    f"View {prod.name} in Demand Forecast",
                    "Inspect ML Model Transparency",
                    "Check Replenishment Recommendations"
                ]
            elif detected_sku:
                prod = products_by_sku[detected_sku]
                confidence = 0.95
                answer = f"🔍 No active ML demand forecast records found in PostgreSQL for **{prod.name} ({detected_sku})** in the specified scope."
                data = {"sku": detected_sku, "product": prod.name, "records_found": 0}
                suggested_actions = ["Run Demand Sensing Pipeline", "View All Forecasts"]
            else:
                confidence = 0.95
                answer = (
                    "📈 **Network ML Demand Forecast Overview**:\n"
                    "The MedCare ML forecaster produces 30-day forward demand projections using multi-signal sensing (RandomForestRegressor).\n\n"
                    "Please specify a pharmaceutical product (e.g. *\"Forecast demand for Paracetamol 500mg in MUM-01\"*) to view detailed demand curves, daily velocity, and confidence intervals."
                )
                data = {
                    "model": "RandomForestRegressor (Multi-Signal Sensing)",
                    "horizon_days": 30,
                    "confidence_average_pct": 87.4,
                    "monitored_products_count": len(products)
                }
                suggested_actions = [
                    "What is the demand forecast for Paracetamol 500mg?",
                    "Forecast for Amoxicillin in DEL-02",
                    "Predict demand for Azithromycin in HYD-01"
                ]
        else:
            prod_name = records[0][1].name if records else detected_sku
            total_proj = sum(fc.final_forecast for fc, p in records)
            avg_conf = sum(fc.confidence_pct for fc, p in records) / max(1, len(records))

            fc_lines = []
            fc_data_list = []
            for fc, p in records[:8]:
                fc_lines.append(
                    f"• **{fc.forecast_date}** ({fc.warehouse_id}): Projected **{int(round(fc.final_forecast)):,} units** (Confidence: {fc.confidence_pct:.1f}%, Trend: {fc.trend_direction})"
                )
                fc_data_list.append({
                    "sku": fc.sku,
                    "product_name": p.name,
                    "warehouse_id": fc.warehouse_id,
                    "forecast_date": str(fc.forecast_date),
                    "final_forecast": fc.final_forecast,
                    "confidence_pct": fc.confidence_pct,
                    "trend_direction": fc.trend_direction,
                    "primary_driver": fc.primary_driver
                })

            confidence = 0.98
            answer = (
                f"📈 **ML Demand Forecast for {prod_name}** ({len(records)} daily intervals):\n"
                f"- **Total Projected Demand**: {int(round(total_proj)):,} units\n"
                f"- **Average Model Confidence**: {avg_conf:.1f}%\n\n"
                f"**Daily Projections**:\n" + "\n".join(fc_lines)
            )
            data = {
                "sku": detected_sku,
                "product_name": prod_name,
                "total_projected_demand": int(round(total_proj)),
                "forecast_records_count": len(records),
                "forecasts": fc_data_list
            }
            suggested_actions = ["Open Demand Forecast Page", "Inspect Model Accuracy & Lineage"]

    # ==========================================
    # INTENT 6: WAREHOUSE & REGIONAL DC STATUS
    # ==========================================
    elif any(w in query_text for w in ["warehouse", "warehouses", "dc", "distribution center", "capacity", "utilization", "tier"]):
        category = "Warehouses"
        if detected_wh:
            w = wh_map[detected_wh]
            inv_sum_res = await db.execute(
                select(func.sum(Inventory.current_stock)).where(Inventory.warehouse_id == detected_wh)
            )
            wh_units = inv_sum_res.scalar() or 0
            confidence = 0.99
            answer = (
                f"🏢 **Distribution Center Details: {w.name} ({w.id})**:\n"
                f"- **Region / Location**: {w.region} ({w.location})\n"
                f"- **Tier**: {w.tier}\n"
                f"- **Current Physical Stock**: {wh_units:,} units\n"
                f"- **Capacity**: {w.capacity_units:,} units ({w.current_utilization_pct}% utilized)\n"
                f"- **Lead Time**: {w.lead_time_days} days\n"
                f"- **Health Score**: {w.health_score}/100 ({w.status})"
            )
            data = {
                "warehouse_id": detected_wh,
                "name": w.name,
                "location": w.location,
                "region": w.region,
                "tier": w.tier,
                "current_physical_stock": wh_units,
                "capacity_units": w.capacity_units,
                "utilization_pct": w.current_utilization_pct,
                "lead_time_days": w.lead_time_days,
                "health_score": w.health_score,
                "status": w.status
            }
            suggested_actions = [f"View {w.name} Details", "Check Network Capacity"]
        else:
            wh_lines = [
                f"• **{w.name} ({w.id})**: {w.location} | Tier: {w.tier} | Health: {w.status} | Lead Time: {w.lead_time_days}d"
                for w in warehouses
            ]
            wh_data_list = [
                {
                    "warehouse_id": w.id,
                    "name": w.name,
                    "location": w.location,
                    "region": w.region,
                    "tier": w.tier,
                    "capacity_units": w.capacity_units,
                    "utilization_pct": w.current_utilization_pct,
                    "health_score": w.health_score,
                    "status": w.status,
                    "lead_time_days": w.lead_time_days
                }
                for w in warehouses
            ]
            confidence = 0.97
            answer = (
                f"🏢 **Active Regional Distribution Centers** ({len(warehouses)} active nodes):\n\n" +
                "\n".join(wh_lines)
            )
            data = {"active_warehouses_count": len(warehouses), "warehouses": wh_data_list}
            suggested_actions = ["View Warehouses Overview", "Check DC Utilization Trends"]

    # ==========================================
    # FALLBACK GROUNDED INTENT
    # ==========================================
    else:
        category = "General"
        confidence = 0.85
        answer = (
            f"🤖 I am your MedCare SCM Control Tower Assistant connected live to PostgreSQL.\n\n"
            f"You can ask me grounded questions about:\n"
            f"• **Inventory & Stock**: *\"What is the stock of Paracetamol in MUM-01?\"*\n"
            f"• **FEFO & Expiry**: *\"Which batches are expiring soon?\"*\n"
            f"• **Replenishment**: *\"What purchase orders are recommended?\"*\n"
            f"• **Alerts**: *\"Are there any critical stockout alerts?\"*\n"
            f"• **Transactions & Consumption**: *\"Show recent internal consumption records.\"*\n"
            f"• **Warehouses**: *\"What is the capacity of Delhi DC?\"*"
        )
        data = {
            "catalog_product_count": len(products),
            "active_dc_count": len(warehouses),
            "distribution_centers": list(wh_map.keys()),
            "supported_topics": ["Inventory", "FEFO Batches", "Replenishment", "Alerts", "Transactions", "Warehouses"]
        }
        suggested_actions = [
            "What is our total inventory valuation?",
            "Which batches are expiring in the next 60 days?",
            "Show critical alerts",
            "Show recent consumption transactions"
        ]

    # ==========================================
    # SHARED GEMINI REPHRASING BLOCK
    # ==========================================
    if gemini_service.is_available:
        grounded_payload = {
            "category": category,
            "rule_based_summary": answer,
            "database_records": data
        }
        ai_phrased = await gemini_service.phrase_answer(
            user_query=req.query,
            grounded_data=grounded_payload,
            category=category
        )
        if ai_phrased:
            answer = ai_phrased

    return ChatResponse(
        query=req.query,
        answer=answer,
        category=category,
        confidence=confidence,
        data=data,
        suggested_actions=suggested_actions
    )

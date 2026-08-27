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
from backend.app.engines.inventory_engine import InventoryEngine
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
    and returns verified data synthesized with Gemini 2.0 Flash or deterministic rule engine.
    """
    query_text = req.query.strip().lower()
    today = get_today_ist()

    # 1. Pre-load active master catalogs
    prods_res = await db.execute(select(Product).where(Product.is_active != False))
    products = prods_res.scalars().all()
    products_by_sku = {p.sku.upper(): p for p in products}

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

    # If request specifies a warehouse filter explicitly
    if req.warehouse and req.warehouse != "All" and req.warehouse.upper() in wh_map:
        detected_wh = req.warehouse.upper()

    answer: str = ""
    category: str = "General"
    confidence: float = 0.95
    data: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None

    # =========================================================================
    # INTENT 1: LOW STOCK & REORDER NEEDED QUERIES
    # =========================================================================
    is_low_stock_query = any(phrase in query_text for phrase in [
        "low stock", "low inventory", "which products are low", "what is low",
        "what items are low", "items low", "low on stock", "below reorder",
        "below rop", "what needs to be reordered", "what to reorder", "reorder needed",
        "need reorder", "needs replenishment", "running low", "short supply",
        "short on stock", "low quantity", "replenish needed", "which are low",
        "show low", "show me low"
    ])

    # =========================================================================
    # INTENT 2: STOCKOUT / CRITICAL SHORTAGE QUERIES
    # =========================================================================
    is_stockout_query = any(phrase in query_text for phrase in [
        "stockout", "stock out", "out of stock", "zero stock", "depleted",
        "critical stock", "critical items", "critical inventory", "below safety stock",
        "no stock", "empty stock", "severe shortage", "stockouts"
    ])

    # =========================================================================
    # INTENT 3: OVERSTOCK / SURPLUS INVENTORY QUERIES
    # =========================================================================
    is_overstock_query = any(phrase in query_text for phrase in [
        "overstock", "overstocked", "excess inventory", "excess stock",
        "surplus stock", "surplus inventory", "too much stock", "high stock",
        "slow moving", "over stock"
    ])

    # =========================================================================
    # INTENT 4: REORDER POINT & SAFETY STOCK CONFIGURATION QUERIES
    # =========================================================================
    is_rop_config_query = any(phrase in query_text for phrase in [
        "reorder point", "rop of", "rop for", "safety stock for", "safety stock of",
        "reorder threshold", "safety buffer", "inventory policy", "min order qty",
        "minimum order quantity", "moq of", "moq for"
    ])

    # Execute specific query logic based on classified intent:

    if is_low_stock_query:
        category = "Low Stock"
        inv_query = (
            select(Inventory, Product, Warehouse)
            .join(Product, Inventory.sku == Product.sku)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(
                Warehouse.is_active != False,
                Product.is_active != False,
                Inventory.current_stock <= Inventory.reorder_point
            )
        )
        if detected_sku:
            inv_query = inv_query.where(Inventory.sku == detected_sku)
        if detected_wh:
            inv_query = inv_query.where(Inventory.warehouse_id == detected_wh)

        inv_query = inv_query.order_by(
            (Inventory.current_stock - Inventory.reorder_point).asc(),
            Inventory.current_stock.asc()
        )
        res = await db.execute(inv_query)
        low_items = res.all()

        if not low_items:
            scope_desc = f"in {wh_map[detected_wh].name} ({detected_wh})" if detected_wh else "across the network"
            if detected_sku:
                prod = products_by_sku[detected_sku]
                answer = f"✅ **{prod.name} ({detected_sku})** is currently **above** its reorder threshold {scope_desc}. No low-stock condition is detected."
            else:
                answer = f"✅ **No Low Stock Items**: All active pharmaceutical inventory items {scope_desc} are currently operating above their configured Reorder Points (ROP)."
            data = {"low_stock_count": 0, "scope": detected_wh or "All Warehouses", "items": []}
            suggested_actions = ["View Inventory Dashboard", "Check Replenishment Recommendations", "View All Stock Levels"]
        else:
            lines = []
            item_data_list = []
            for inv, prod, wh in low_items[:10]:
                status_formatted, _ = InventoryEngine.evaluate_inventory_status(inv.current_stock, inv.reorder_point, inv.safety_stock)
                status_formatted = status_formatted.replace("_", " ").title()
                lines.append(
                    f"• **{prod.name}** (`{prod.sku}`) @ **{wh.id}** ({wh.name}):\n"
                    f"  - **Current Stock**: {inv.current_stock:,} {prod.unit or 'Units'}\n"
                    f"  - **Reorder Point (ROP)**: {inv.reorder_point:,} | **Safety Stock**: {inv.safety_stock:,}\n"
                    f"  - **Days of Cover**: {inv.days_of_cover:.1f}d | **Status**: {status_formatted}"
                )
                item_data_list.append({
                    "sku": prod.sku,
                    "product_name": prod.name,
                    "category": prod.category,
                    "warehouse_id": wh.id,
                    "warehouse_name": wh.name,
                    "current_stock": inv.current_stock,
                    "reorder_point": inv.reorder_point,
                    "safety_stock": inv.safety_stock,
                    "days_of_cover": inv.days_of_cover,
                    "status": status_formatted,
                    "unit": prod.unit or "Units"
                })

            scope_title = f"in {wh_map[detected_wh].name} ({detected_wh})" if detected_wh else "Across Network"
            total_count = len(low_items)
            more_text = f"\n*...and {total_count - 10} more low stock items in database.*" if total_count > 10 else ""

            answer = (
                f"⚠️ **Low Stock Inventory Items ({total_count} records {scope_title})**:\n"
                f"The following products are at or below their configured Reorder Point:\n\n"
                + "\n\n".join(lines)
                + more_text
            )
            data = {
                "low_stock_count": total_count,
                "scope": detected_wh or "All Warehouses",
                "items": item_data_list
            }
            suggested_actions = [
                "Review Replenishment Recommendations",
                "Approve Purchase Orders",
                "Check Cross-DC Transfers"
            ]

    elif is_stockout_query:
        category = "Stockouts & Critical Shortages"
        crit_query = (
            select(Inventory, Product, Warehouse)
            .join(Product, Inventory.sku == Product.sku)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(
                Warehouse.is_active != False,
                Product.is_active != False,
                or_(
                    Inventory.current_stock <= 0,
                    Inventory.current_stock < Inventory.safety_stock
                )
            )
        )
        if detected_sku:
            crit_query = crit_query.where(Inventory.sku == detected_sku)
        if detected_wh:
            crit_query = crit_query.where(Inventory.warehouse_id == detected_wh)

        crit_query = crit_query.order_by(Inventory.current_stock.asc())
        crit_res = await db.execute(crit_query)
        crit_items = crit_res.all()

        if not crit_items:
            scope_desc = f"in {wh_map[detected_wh].name} ({detected_wh})" if detected_wh else "across all distribution centers"
            answer = f"✅ **Zero Stockouts Detected**: No pharmaceutical items are currently out of stock or below their safety stock buffer {scope_desc}."
            data = {"critical_stockout_count": 0, "scope": detected_wh or "Network", "items": []}
            suggested_actions = ["View Inventory Status", "Check Active Alerts"]
        else:
            lines = []
            item_data_list = []
            for inv, prod, wh in crit_items[:8]:
                status_formatted, _ = InventoryEngine.evaluate_inventory_status(inv.current_stock, inv.reorder_point, inv.safety_stock)
                status_formatted = status_formatted.replace("_", " ").title()
                lines.append(
                    f"• **{prod.name}** (`{prod.sku}`) @ **{wh.id}**:\n"
                    f"  - **Current Stock**: {inv.current_stock:,} units (Safety Stock Buffer: {inv.safety_stock:,})\n"
                    f"  - **Reorder Point**: {inv.reorder_point:,} | **Status**: {status_formatted}"
                )
                item_data_list.append({
                    "sku": prod.sku,
                    "product_name": prod.name,
                    "warehouse_id": wh.id,
                    "warehouse_name": wh.name,
                    "current_stock": inv.current_stock,
                    "safety_stock": inv.safety_stock,
                    "reorder_point": inv.reorder_point,
                    "status": status_formatted
                })

            answer = (
                f"🚨 **Critical Shortages & Stockout Items ({len(crit_items)} items requiring immediate inbound)**:\n\n"
                + "\n\n".join(lines)
            )
            data = {"critical_count": len(crit_items), "items": item_data_list}
            suggested_actions = ["Approve Emergency Replenishment", "Check Inter-DC Transfers", "View Critical Alerts"]

    elif is_overstock_query:
        category = "Overstock"
        over_query = (
            select(Inventory, Product, Warehouse)
            .join(Product, Inventory.sku == Product.sku)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(
                Warehouse.is_active != False,
                Product.is_active != False,
                Inventory.current_stock > Inventory.reorder_point * 1.8
            )
        )
        if detected_sku:
            over_query = over_query.where(Inventory.sku == detected_sku)
        if detected_wh:
            over_query = over_query.where(Inventory.warehouse_id == detected_wh)

        over_query = over_query.order_by((Inventory.current_stock / func.max(1, Inventory.reorder_point)).desc())
        over_res = await db.execute(over_query)
        over_items = over_res.all()

        if not over_items:
            scope_desc = f"in {wh_map[detected_wh].name} ({detected_wh})" if detected_wh else "across all active warehouses"
            answer = f"✅ **No Overstocked Items**: All inventory holding levels {scope_desc} are within optimal capacity parameters."
            data = {"overstock_count": 0, "scope": detected_wh or "Network", "items": []}
            suggested_actions = ["View Inventory Overview", "Check Space Utilization"]
        else:
            lines = []
            item_data_list = []
            for inv, prod, wh in over_items[:8]:
                ratio = round(inv.current_stock / max(1, inv.reorder_point), 1)
                lines.append(
                    f"• **{prod.name}** (`{prod.sku}`) @ **{wh.id}**:\n"
                    f"  - **Current Stock**: {inv.current_stock:,} units ({ratio}x Reorder Point: {inv.reorder_point:,})\n"
                    f"  - **Days of Cover**: {inv.days_of_cover:.1f}d | **Safety Stock**: {inv.safety_stock:,}"
                )
                item_data_list.append({
                    "sku": prod.sku,
                    "product_name": prod.name,
                    "warehouse_id": wh.id,
                    "current_stock": inv.current_stock,
                    "reorder_point": inv.reorder_point,
                    "ratio_to_rop": ratio,
                    "days_of_cover": inv.days_of_cover
                })

            answer = (
                f"📦 **Overstocked Inventory Records ({len(over_items)} items above 1.8x ROP)**:\n\n"
                + "\n\n".join(lines)
            )
            data = {"overstock_count": len(over_items), "items": item_data_list}
            suggested_actions = ["Recommend Outbound Transfers", "Adjust Procurement Schedules"]

    elif is_rop_config_query and detected_sku:
        category = "Inventory Policy"
        prod = products_by_sku[detected_sku]
        inv_query = (
            select(Inventory, Warehouse)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False, Inventory.sku == detected_sku)
        )
        if detected_wh:
            inv_query = inv_query.where(Inventory.warehouse_id == detected_wh)

        inv_res = await db.execute(inv_query)
        inv_configs = inv_res.all()

        if not inv_configs:
            answer = f"ℹ️ Product **{prod.name} ({detected_sku})** has default catalog Reorder Point: **{prod.default_reorder_point:,}**, Safety Stock: **{prod.default_safety_stock:,}**, MOQ: **{prod.moq:,}**."
            data = {"sku": detected_sku, "product_name": prod.name, "default_rop": prod.default_reorder_point, "default_ss": prod.default_safety_stock}
        else:
            lines = [
                f"• **{wh.id}** ({wh.name}): ROP = **{inv.reorder_point:,}** units | Safety Stock = **{inv.safety_stock:,}** units | Current Stock = **{inv.current_stock:,}** units"
                for inv, wh in inv_configs
            ]
            config_data = [
                {
                    "warehouse_id": wh.id,
                    "reorder_point": inv.reorder_point,
                    "safety_stock": inv.safety_stock,
                    "current_stock": inv.current_stock,
                    "status": inv.status
                }
                for inv, wh in inv_configs
            ]
            answer = (
                f"⚙️ **Inventory Policy & Thresholds for {prod.name} ({detected_sku})**:\n"
                f"- **Catalog Unit Price**: ₹{prod.unit_cost:.2f}\n"
                f"- **Minimum Order Qty (MOQ)**: {prod.moq:,} {prod.unit or 'Units'}\n\n"
                f"**Warehouse-Specific Thresholds**:\n"
                + "\n".join(lines)
            )
            data = {
                "sku": detected_sku,
                "product_name": prod.name,
                "moq": prod.moq,
                "unit_cost": prod.unit_cost,
                "warehouse_policies": config_data
            }
            suggested_actions = [f"Edit {prod.name} Settings", "Check Stock Level"]

    # =========================================================================
    # INTENT 5: FEFO & EXPIRY RISK QUERIES
    # =========================================================================
    elif any(w in query_text for w in ["fefo", "expiry", "expire", "expiring", "near expiry", "batch", "shelf life"]):
        category = "FEFO & Expiry"
        b_query = (
            select(Batch, Product, Warehouse)
            .join(Product, Batch.sku == Product.sku)
            .join(Warehouse, Batch.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False, Batch.quantity > 0, Batch.expiry_date > today)
        )
        if detected_sku:
            b_query = b_query.where(Batch.sku == detected_sku)
        if detected_wh:
            b_query = b_query.where(Batch.warehouse_id == detected_wh)

        b_query = b_query.order_by(Batch.expiry_date.asc())
        b_res = await db.execute(b_query)
        batches = b_res.all()

        if not batches:
            answer = "✅ No active near-expiry batches detected in PostgreSQL for the requested scope."
            data = {"batches_found": 0}
            suggested_actions = ["View Batches Report", "Check FEFO Balancing"]
        else:
            batch_lines = []
            batch_data_list = []
            for b, p, wh in batches[:8]:
                days_left = (b.expiry_date - today).days
                batch_lines.append(
                    f"• **Batch {b.id}** ({p.name} @ {wh.id}): {b.quantity:,} units | Expiry: **{b.expiry_date}** ({days_left}d remaining) | Status: `{b.status}`"
                )
                batch_data_list.append({
                    "batch_id": b.id,
                    "sku": b.sku,
                    "product_name": p.name,
                    "warehouse_id": wh.id,
                    "quantity": b.quantity,
                    "available_quantity": b.available_quantity,
                    "expiry_date": str(b.expiry_date),
                    "days_until_expiry": days_left,
                    "status": b.status
                })

            answer = (
                f"⏳ **FEFO Batch Dispatch Priority (Earliest Expiry First)**:\n"
                f"Active batches sorted strictly by expiration date:\n\n"
                + "\n".join(batch_lines)
            )
            data = {"total_batches_in_scope": len(batches), "batches": batch_data_list}
            suggested_actions = ["Open Transfers & FEFO Balancing Tab", "Check Batch Expiry Schedule"]

    # =========================================================================
    # INTENT 6: REPLENISHMENT & PURCHASE ORDERS QUERIES
    # =========================================================================
    elif any(w in query_text for w in ["replenish", "replenishment", "purchase order", "po", "transfer", "procure", "procurement"]):
        category = "Replenishment"
        rec_query = (
            select(ReplenishmentRecommendation, Product, Warehouse)
            .join(Product, ReplenishmentRecommendation.sku == Product.sku)
            .join(Warehouse, ReplenishmentRecommendation.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False, ReplenishmentRecommendation.status == "PENDING")
        )
        if detected_wh:
            rec_query = rec_query.where(ReplenishmentRecommendation.warehouse_id == detected_wh)
        if detected_sku:
            rec_query = rec_query.where(ReplenishmentRecommendation.sku == detected_sku)

        recs_res = await db.execute(rec_query)
        recs = recs_res.all()

        trf_query = (
            select(InventoryTransfer, Product)
            .join(Product, InventoryTransfer.sku == Product.sku)
            .where(InventoryTransfer.status == "RECOMMENDED")
        )
        trf_res = await db.execute(trf_query)
        transfers = trf_res.all()

        rec_lines = []
        rec_data_list = []
        for r, p, wh in recs[:6]:
            rec_lines.append(
                f"• **{p.name} ({r.sku}) @ {wh.id}**: Order **{r.recommended_quantity:,} units** via {r.decision_type} (Est: ₹{r.estimated_cost_inr/100000:.1f} L) — Priority: **{r.priority.upper()}**"
            )
            rec_data_list.append({
                "sku": r.sku,
                "product_name": p.name,
                "warehouse_id": wh.id,
                "recommended_quantity": r.recommended_quantity,
                "decision_type": r.decision_type,
                "estimated_cost_inr": r.estimated_cost_inr,
                "priority": r.priority
            })

        trf_lines = [
            f"• **{p.name}**: Transfer {t.quantity:,} units from {t.source_warehouse_id} ➔ {t.destination_warehouse_id} (Avoids ₹{t.estimated_savings_inr:,.0f} procurement cost)"
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

        ans = f"🚚 **Active Replenishment Recommendations** ({len(recs)} pending purchase orders):\n\n"
        if rec_lines:
            ans += "\n".join(rec_lines) + "\n\n"
        else:
            ans += "All inventory levels in scope are above reorder thresholds. No pending purchase orders.\n\n"

        if trf_lines:
            ans += f"🔄 **Inter-DC FEFO Balancing Transfers**:\n" + "\n".join(trf_lines)

        answer = ans
        data = {
            "pending_recommendations_count": len(recs),
            "recommendations": rec_data_list,
            "active_transfers_count": len(transfers),
            "transfers": trf_data_list
        }
        suggested_actions = ["Review Replenishment Recommendations"]

    # =========================================================================
    # INTENT 7: ALERTS & SHORTAGE RISKS QUERIES
    # =========================================================================
    elif any(w in query_text for w in ["alert", "alerts", "warning", "risk", "escalation"]):
        category = "Alerts"
        al_query = (
            select(Alert)
            .join(Warehouse, Alert.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False, Alert.status != "Resolved")
        )
        if detected_wh:
            al_query = al_query.where(Alert.warehouse_id == detected_wh)
        if detected_sku:
            al_query = al_query.where(Alert.sku == detected_sku)

        al_query = al_query.order_by(Alert.severity.desc(), Alert.created_at.desc())
        al_res = await db.execute(al_query)
        active_alerts = al_res.scalars().all()

        if not active_alerts:
            answer = "🎉 **Zero Active Alerts**: All distribution centers are operating within safe inventory, capacity, and expiry thresholds."
            data = {"active_alerts": 0}
            suggested_actions = ["View Alerts Dashboard"]
        else:
            alert_lines = [
                f"• **[{a.severity.upper()}] {a.alert_type}** ({a.sku or 'Network'} @ {a.warehouse_id}): {a.detail} (Status: `{a.status}`)"
                for a in active_alerts[:6]
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

            answer = (
                f"🚨 **Active Supply Chain Alerts ({len(active_alerts)} unresolved)**:\n\n"
                + "\n".join(alert_lines)
            )
            data = {"total_active_alerts": len(active_alerts), "alerts": alert_data_list}
            suggested_actions = ["View Alerts Dashboard", "Acknowledge Critical Alerts"]

    # =========================================================================
    # INTENT 8: TRANSACTIONS & CONSUMPTION QUERIES
    # =========================================================================
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

            answer = (
                f"📝 **Recent Inventory Transactions & Ledger ({len(txs)} records)**:\n\n"
                + "\n".join(tx_lines)
            )
            data = {"total_transactions": len(txs), "recent_transactions": tx_data_list}
            suggested_actions = ["Open Inventory Audit Ledger", "Record Stock Transaction"]

    # =========================================================================
    # INTENT 9: DEMAND FORECAST QUERIES
    # =========================================================================
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
            ml_data = None
            if detected_sku:
                try:
                    wh_target = detected_wh or "MUM-01"
                    ml_data = await PredictionService.predict_demand(db, detected_sku, wh_target, 30)
                except Exception:
                    ml_data = None

            if ml_data and ml_data.get("forecast_demand_next_30d"):
                prod = products_by_sku[detected_sku]
                wh_target = detected_wh or "MUM-01"
                total_30d = ml_data.get("forecast_demand_next_30d", 0)
                sensed_daily = ml_data.get("sensed_daily", 0.0)
                confidence_pct = ml_data.get("confidence_level_pct", 87.4)
                trend = ml_data.get("trend_direction", "Stable")
                driver = ml_data.get("primary_driver", "Baseline Dispensing Velocity")
                peak_date = ml_data.get("predicted_peak_date", "")
                peak_units = ml_data.get("predicted_peak_units", 0)

                answer = (
                    f"📈 **ML Demand Forecast for {prod.name} ({detected_sku}) @ {wh_target}**:\n"
                    f"- **30-Day Projected Demand**: {total_30d:,} units\n"
                    f"- **Sensed Daily Velocity**: {sensed_daily:.1f} units/day\n"
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
            else:
                answer = (
                    "📈 **Network ML Demand Forecast Overview**:\n"
                    "The MedCare ML forecaster produces 30-day forward demand projections using multi-signal sensing (RandomForestRegressor).\n\n"
                    "Please specify a pharmaceutical product (e.g. *\"Forecast demand for Paracetamol in MUM-01\"*) to view detailed demand curves, daily velocity, and confidence intervals."
                )
                data = {
                    "model": "RandomForestRegressor (Multi-Signal Sensing)",
                    "horizon_days": 30,
                    "confidence_average_pct": 87.4,
                    "monitored_products_count": len(products)
                }
                suggested_actions = [
                    "What is the demand forecast for Paracetamol?",
                    "Forecast for Amoxicillin in DEL-02",
                    "Predict demand for Azithromycin"
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

    # =========================================================================
    # INTENT 10: SPECIFIC PRODUCT / SKU STOCK & AVAILABILITY QUERY
    # =========================================================================
    elif detected_sku:
        category = "Product Inventory"
        prod = products_by_sku[detected_sku]
        inv_query = (
            select(Inventory, Warehouse)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False, Inventory.sku == detected_sku)
        )
        if detected_wh:
            inv_query = inv_query.where(Inventory.warehouse_id == detected_wh)

        inv_res = await db.execute(inv_query)
        inv_list = inv_res.all()

        if not inv_list:
            answer = f"No active inventory records found in database for **{prod.name} ({detected_sku})** in the specified warehouse scope."
            data = {"sku": detected_sku, "product": prod.name, "records_found": 0}
            suggested_actions = ["View all inventory", "Check other distribution centers"]
        else:
            total_st = sum(inv.current_stock for inv, wh in inv_list)
            total_avail = sum(inv.available_stock for inv, wh in inv_list)
            breakdowns = [
                f"• **{wh.id}** ({wh.name}): **{inv.current_stock:,}** units (Available: {inv.available_stock:,}, ROP: {inv.reorder_point:,}, Safety Stock: {inv.safety_stock:,}) | Status: `{inv.status.replace('_', ' ').title()}`"
                for inv, wh in inv_list
            ]
            breakdown_dicts = [
                {
                    "warehouse_id": wh.id,
                    "warehouse_name": wh.name,
                    "current_stock": inv.current_stock,
                    "available_stock": inv.available_stock,
                    "reorder_point": inv.reorder_point,
                    "safety_stock": inv.safety_stock,
                    "status": inv.status.replace("_", " ").title(),
                    "days_of_cover": inv.days_of_cover
                }
                for inv, wh in inv_list
            ]

            answer = (
                f"📊 **Inventory Status for {prod.name} ({detected_sku})**:\n"
                f"- **Category**: {prod.category}\n"
                f"- **Total Physical Stock**: **{total_st:,} {prod.unit or 'Units'}**\n"
                f"- **Available for Dispensing**: **{total_avail:,} units**\n"
                f"- **Unit Price**: ₹{prod.unit_cost:.2f}\n"
                f"- **MOQ**: {prod.moq:,} units\n\n"
                f"**Regional Warehouse Breakdown**:\n" + "\n".join(breakdowns)
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
            suggested_actions = [f"View {prod.name} in Inventory", f"Check {detected_sku} Batches"]

    # =========================================================================
    # INTENT 11: WAREHOUSE-SPECIFIC INVENTORY LIST QUERY
    # =========================================================================
    elif detected_wh and any(w in query_text for w in ["stock", "inventory", "products", "stored", "items", "units", "what is in", "what do we have in"]):
        category = "Warehouse Inventory"
        w = wh_map[detected_wh]
        inv_query = (
            select(Inventory, Product)
            .join(Product, Inventory.sku == Product.sku)
            .where(Inventory.warehouse_id == detected_wh, Product.is_active != False)
            .order_by(Inventory.current_stock.desc())
        )
        inv_res = await db.execute(inv_query)
        wh_items = inv_res.all()

        total_units = sum(inv.current_stock for inv, prod in wh_items)
        lines = [
            f"• **{prod.name}** (`{prod.sku}`): {inv.current_stock:,} units (ROP: {inv.reorder_point:,}, Safety: {inv.safety_stock:,}) | Status: `{inv.status.replace('_', ' ').title()}`"
            for inv, prod in wh_items[:8]
        ]
        item_data = [
            {
                "sku": prod.sku,
                "product_name": prod.name,
                "current_stock": inv.current_stock,
                "reorder_point": inv.reorder_point,
                "safety_stock": inv.safety_stock,
                "status": inv.status.replace("_", " ").title()
            }
            for inv, prod in wh_items
        ]

        answer = (
            f"🏢 **Inventory in {w.name} ({w.id})**:\n"
            f"- **Total Physical Units**: {total_units:,} units\n"
            f"- **Tracked SKUs**: {len(wh_items)} products\n"
            f"- **Capacity Utilization**: {w.current_utilization_pct}%\n\n"
            f"**Stocked Products**:\n"
            + "\n".join(lines)
        )
        data = {
            "warehouse_id": w.id,
            "warehouse_name": w.name,
            "total_physical_stock": total_units,
            "sku_count": len(wh_items),
            "items": item_data
        }
        suggested_actions = [f"View {w.name} in Inventory", "Show Low Stock in this DC"]

    # =========================================================================
    # INTENT 12: WAREHOUSES OVERVIEW & CAPACITY STATUS
    # =========================================================================
    elif any(w in query_text for w in ["warehouse", "warehouses", "dc", "distribution center", "capacity", "utilization", "tier", "facility"]):
        category = "Warehouses"
        if detected_wh:
            w = wh_map[detected_wh]
            inv_sum_res = await db.execute(
                select(func.sum(Inventory.current_stock)).where(Inventory.warehouse_id == detected_wh)
            )
            wh_units = inv_sum_res.scalar() or 0
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
                f"• **{w.name} ({w.id})**: {w.location} | Tier: {w.tier} | Health: `{w.status}` | Utilization: {w.current_utilization_pct}%"
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
            answer = (
                f"🏢 **Active Regional Distribution Centers ({len(warehouses)} nodes)**:\n\n"
                + "\n".join(wh_lines)
            )
            data = {"active_warehouses_count": len(warehouses), "warehouses": wh_data_list}
            suggested_actions = ["View Warehouses Overview", "Check DC Utilization"]

    # =========================================================================
    # INTENT 13: GENERAL NETWORK INVENTORY OVERVIEW
    # =========================================================================
    elif any(w in query_text for w in ["stock", "inventory", "units", "how many", "quantity", "count", "valuation", "total inventory"]):
        category = "Inventory"
        total_inv_res = await db.execute(
            select(func.sum(Inventory.current_stock), func.count(Inventory.id)).join(
                Warehouse, Inventory.warehouse_id == Warehouse.id
            ).where(Warehouse.is_active != False)
        )
        t_units, t_count = total_inv_res.one()
        t_units = t_units or 0

        # Calculate low stock and stockout counts for accurate summary
        low_res = await db.execute(
            select(func.count(Inventory.id)).join(Warehouse, Inventory.warehouse_id == Warehouse.id).where(
                Warehouse.is_active != False,
                Inventory.current_stock <= Inventory.reorder_point
            )
        )
        low_count = low_res.scalar() or 0

        answer = (
            f"📦 **Network Inventory Overview**:\n"
            f"- **Total Physical Stock**: **{t_units:,} units**\n"
            f"- **Active SKU-DC Relationships**: **{t_count} records** across {len(warehouses)} DCs\n"
            f"- **Low Stock SKUs (Below ROP)**: **{low_count} items**\n\n"
            f"💡 *Ask **\"Show low stock\"** or **\"Stock of Paracetamol\"** for item-level granularity.*"
        )
        data = {
            "total_units": t_units,
            "active_items_count": t_count,
            "low_stock_count": low_count,
            "active_dcs": len(warehouses),
            "distribution_centers": list(wh_map.keys())
        }
        suggested_actions = ["Show Low Stock Items", "Show Out of Stock Items", "Show Overstock Items"]

    # =========================================================================
    # INTENT 14: DEFAULT SCM KNOWLEDGE ASSISTANT FALLBACK
    # =========================================================================
    else:
        category = "General"
        answer = (
            f"🤖 I am your MedCare SCM Control Tower Assistant connected live to PostgreSQL.\n\n"
            f"You can ask me grounded questions about:\n"
            f"• **Low Stock & Shortages**: *\"Show low stock\"* or *\"What needs to be reordered?\"*\n"
            f"• **Stockouts**: *\"Show out of stock items\"*\n"
            f"• **Overstock**: *\"Show overstocked inventory\"*\n"
            f"• **Product Stock**: *\"What is the stock of Paracetamol in MUM-01?\"*\n"
            f"• **FEFO & Expiry**: *\"Which batches are expiring soon?\"*\n"
            f"• **Replenishment**: *\"What purchase orders are recommended?\"*\n"
            f"• **Alerts**: *\"Are there any critical alerts?\"*\n"
            f"• **Warehouses**: *\"Show inventory in Mumbai DC\"*"
        )
        data = {
            "catalog_product_count": len(products),
            "active_dc_count": len(warehouses),
            "distribution_centers": list(wh_map.keys()),
            "supported_topics": ["Low Stock", "Stockouts", "Overstock", "Inventory", "FEFO Batches", "Replenishment", "Alerts", "Warehouses"]
        }
        suggested_actions = [
            "Show low stock",
            "Show out of stock",
            "Which batches are expiring soon?",
            "What purchase orders are recommended?"
        ]

    # =========================================================================
    # SHARED GEMINI REPHRASING BLOCK (STRICTLY GROUNDED TO LIVE DB RECORDS)
    # =========================================================================
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

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
    Analyzes user queries and answers with exact real-time PostgreSQL database state.
    Covers inventory, SKU stock, warehouses, replenishment, FEFO, alerts, transactions, and consumption.
    """
    query_text = req.query.strip().lower()
    today = date(2026, 8, 24)

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

    # ==========================================
    # INTENT 1: INVENTORY & STOCK LEVEL QUERY
    # ==========================================
    if any(w in query_text for w in ["stock", "inventory", "units", "available", "quantity", "how many", "count"]):
        if detected_sku:
            prod = products_by_sku[detected_sku]
            inv_query = select(Inventory).where(Inventory.sku == detected_sku)
            if detected_wh:
                inv_query = inv_query.where(Inventory.warehouse_id == detected_wh)
            inv_res = await db.execute(inv_query)
            inv_list = inv_res.scalars().all()

            if not inv_list:
                return ChatResponse(
                    query=req.query,
                    category="Inventory",
                    confidence=0.98,
                    answer=f"No active inventory records found in PostgreSQL for **{prod.name} ({detected_sku})** in the specified warehouse scope.",
                    data={"sku": detected_sku, "product": prod.name}
                )

            total_st = sum(i.current_stock for i in inv_list)
            total_avail = sum(i.available_stock for i in inv_list)
            breakdowns = [f"• **{i.warehouse_id}**: {i.current_stock:,} units ({i.status.replace('_', ' ').title()})" for i in inv_list]

            ans = (
                f"📊 **Inventory Status for {prod.name} ({detected_sku})**:\n"
                f"- **Total Physical Stock**: {total_st:,} units\n"
                f"- **Available for Dispensing**: {total_avail:,} units\n"
                f"- **Unit Cost**: ₹{prod.unit_cost}\n\n"
                f"**Regional DC Breakdown**:\n" + "\n".join(breakdowns)
            )
            return ChatResponse(
                query=req.query,
                category="Inventory",
                confidence=0.99,
                answer=ans,
                data={"sku": detected_sku, "total_stock": total_st, "records": len(inv_list)},
                suggested_actions=[f"View {prod.name} in Inventory", f"Check {detected_sku} batches"]
            )

        # General inventory overview
        total_inv_res = await db.execute(
            select(func.sum(Inventory.current_stock), func.count(Inventory.id)).join(
                Warehouse, Inventory.warehouse_id == Warehouse.id
            ).where(Warehouse.is_active != False)
        )
        t_units, t_count = total_inv_res.one()
        t_units = t_units or 0

        return ChatResponse(
            query=req.query,
            category="Inventory",
            confidence=0.95,
            answer=(
                f"📦 **Network Inventory Overview**:\n"
                f"- Total active items across network: **{t_count} SKU-DC pairs**\n"
                f"- Total physical stock in active warehouses: **{t_units:,} units**\n"
                f"- Active Distribution Centers: **{len(warehouses)} nodes** ({', '.join(wh_map.keys())})"
            ),
            data={"total_units": t_units, "active_dcs": len(warehouses)}
        )

    # ==========================================
    # INTENT 2: FEFO & EXPIRY RISK QUERY
    # ==========================================
    if any(w in query_text for w in ["fefo", "expiry", "expire", "expiring", "near expiry", "batch", "shelf life"]):
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
            return ChatResponse(
                query=req.query,
                category="FEFO & Expiry",
                confidence=0.95,
                answer="✅ No active near-expiry batches detected in PostgreSQL for the requested scope."
            )

        batch_lines = []
        for idx, (b, p) in enumerate(batches[:6], 1):
            days_left = (b.expiry_date - today).days
            batch_lines.append(
                f"{idx}. **Batch {b.id}** ({p.name} @ {b.warehouse_id}): {b.quantity:,} units | Expiry: {b.expiry_date} ({days_left}d left)"
            )

        ans = (
            f"⏳ **FEFO Batch Dispatch Priority (Earliest Expiry First)**:\n"
            f"Active valid batches sorted strictly by expiration date:\n\n" +
            "\n".join(batch_lines) +
            "\n\n*Note: Expired batches and zero-quantity records are automatically excluded.*"
        )
        return ChatResponse(
            query=req.query,
            category="FEFO & Expiry",
            confidence=0.98,
            answer=ans,
            data={"batches_found": len(batches)},
            suggested_actions=["Open Transfers & FEFO Balancing Tab", "Check Batch Expiry Report"]
        )

    # ==========================================
    # INTENT 3: REPLENISHMENT & TRANSFERS QUERY
    # ==========================================
    if any(w in query_text for w in ["replenish", "replenishment", "order", "purchase order", "po", "transfer", "reorder", "procure"]):
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
        for r, p in recs[:5]:
            rec_lines.append(
                f"• **{p.name} ({r.sku}) @ {r.warehouse_id}**: Order **{r.recommended_quantity:,} units** via {r.decision_type} (Est: ₹{r.estimated_cost_inr/100000:.1f} L) — Priority: {r.priority.upper()}"
            )

        trf_lines = [
            f"• **{p.name}**: Transfer {t.quantity:,} units from {t.source_warehouse_id} ➔ {t.destination_warehouse_id} (Avoids ₹{t.estimated_savings_inr:,.0f} new procurement)"
            for t, p in transfers[:3]
        ]

        ans = f"🚚 **Active Replenishment Recommendations** ({len(recs)} pending):\n\n"
        if rec_lines:
            ans += "\n".join(rec_lines) + "\n\n"
        else:
            ans += "All inventory levels in scope are above reorder thresholds.\n\n"

        if trf_lines:
            ans += f"🔄 **Inter-DC FEFO Balancing Transfers**:\n" + "\n".join(trf_lines)

        return ChatResponse(
            query=req.query,
            category="Replenishment",
            confidence=0.98,
            answer=ans,
            data={"pending_recs": len(recs), "active_transfers": len(transfers)},
            suggested_actions=["Review Replenishment Recommendations", "Approve 1-Click POs"]
        )

    # ==========================================
    # INTENT 4: ALERTS & SHORTAGE RISKS
    # ==========================================
    if any(w in query_text for w in ["alert", "alerts", "critical", "warning", "risk", "stockout", "shortage", "escalation"]):
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
            return ChatResponse(
                query=req.query,
                category="Alerts",
                confidence=0.97,
                answer="🎉 **Zero Active Alerts**: All distribution centers are operating within safe inventory and expiry thresholds.",
                data={"active_alerts": 0}
            )

        alert_lines = [
            f"• **[{a.severity.upper()}] {a.alert_type}** ({a.sku or 'Network'} @ {a.warehouse_id}): {a.detail} (Status: {a.status})"
            for a in active_alerts[:5]
        ]

        ans = (
            f"🚨 **Active Supply Chain Alerts** ({len(active_alerts)} unresolved):\n\n" +
            "\n".join(alert_lines)
        )
        return ChatResponse(
            query=req.query,
            category="Alerts",
            confidence=0.99,
            answer=ans,
            data={"active_alerts": len(active_alerts)},
            suggested_actions=["View Alerts Dashboard", "Acknowledge Critical Alerts"]
        )

    # ==========================================
    # INTENT 5: TRANSACTIONS & INTERNAL CONSUMPTION
    # ==========================================
    if any(w in query_text for w in ["transaction", "transactions", "sale", "receipt", "consumption", "dispensing", "audit log", "movement"]):
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
            return ChatResponse(
                query=req.query,
                category="Transactions",
                confidence=0.96,
                answer="📋 No inventory transactions matching the specified criteria were found in PostgreSQL ledger.",
                data={"transactions_found": 0}
            )

        tx_lines = []
        for t in txs[:6]:
            p_obj = products_by_sku.get(t.sku)
            p_name = p_obj.name if p_obj else t.sku
            tx_lines.append(
                f"• **[{t.transaction_type}] {p_name} @ {t.warehouse_id}**: {t.quantity:+,} units ({t.previous_stock} ➔ {t.new_stock}) | {t.reason or 'Standard movement'} ({t.timestamp.strftime('%d %b %H:%M')})"
            )

        ans = (
            f"📝 **Recent Inventory Transactions & Consumption Ledger** ({len(txs)} records):\n\n" +
            "\n".join(tx_lines)
        )
        return ChatResponse(
            query=req.query,
            category="Transactions",
            confidence=0.98,
            answer=ans,
            data={"total_transactions": len(txs)},
            suggested_actions=["Open Inventory Audit Ledger", "Record Stock Transaction"]
        )

    # ==========================================
    # INTENT 6: WAREHOUSE & REGIONAL DC STATUS
    # ==========================================
    if any(w in query_text for w in ["warehouse", "warehouses", "dc", "distribution center", "capacity", "utilization", "tier"]):
        if detected_wh:
            w = wh_map[detected_wh]
            inv_sum_res = await db.execute(
                select(func.sum(Inventory.current_stock)).where(Inventory.warehouse_id == detected_wh)
            )
            wh_units = inv_sum_res.scalar() or 0
            ans = (
                f"🏢 **Distribution Center Details: {w.name} ({w.id})**:\n"
                f"- **Region / Location**: {w.region} ({w.location})\n"
                f"- **Tier**: {w.tier}\n"
                f"- **Current Physical Stock**: {wh_units:,} units\n"
                f"- **Capacity**: {w.capacity_units:,} units ({w.current_utilization_pct}% utilized)\n"
                f"- **Lead Time**: {w.lead_time_days} days\n"
                f"- **Health Score**: {w.health_score}/100 ({w.status})"
            )
            return ChatResponse(
                query=req.query,
                category="Warehouses",
                confidence=0.99,
                answer=ans,
                data={"warehouse_id": detected_wh, "stock": wh_units}
            )

        wh_lines = [
            f"• **{w.name} ({w.id})**: {w.location} | Tier: {w.tier} | Health: {w.status} | Lead Time: {w.lead_time_days}d"
            for w in warehouses
        ]
        ans = (
            f"🏢 **Active Regional Distribution Centers** ({len(warehouses)} active nodes):\n\n" +
            "\n".join(wh_lines)
        )
        return ChatResponse(
            query=req.query,
            category="Warehouses",
            confidence=0.97,
            answer=ans,
            data={"active_warehouses": len(warehouses)}
        )

    # ==========================================
    # FALLBACK GROUNDED RESPONSE
    # ==========================================
    return ChatResponse(
        query=req.query,
        category="General",
        confidence=0.85,
        answer=(
            f"🤖 I am your MedCare SCM Control Tower Assistant connected live to PostgreSQL.\n\n"
            f"You can ask me grounded questions about:\n"
            f"• **Inventory & Stock**: *\"What is the stock of Paracetamol in MUM-01?\"*\n"
            f"• **FEFO & Expiry**: *\"Which batches are expiring soon?\"*\n"
            f"• **Replenishment**: *\"What purchase orders are recommended?\"*\n"
            f"• **Alerts**: *\"Are there any critical stockout alerts?\"*\n"
            f"• **Transactions & Consumption**: *\"Show recent internal consumption records.\"*\n"
            f"• **Warehouses**: *\"What is the capacity of Delhi DC?\"*"
        ),
        suggested_actions=[
            "What is our total inventory valuation?",
            "Which batches are expiring in the next 60 days?",
            "Show critical alerts",
            "Show recent consumption transactions"
        ]
    )

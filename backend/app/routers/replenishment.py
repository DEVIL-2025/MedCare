from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta, timezone

from backend.app.database import get_db
from backend.app.models.replenishment import ReplenishmentRecommendation, PurchaseOrder
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.routers.ws import ws_manager

router = APIRouter(prefix="/api/replenishment", tags=["Replenishment"])


@router.get("/fefo-batches")
async def get_fefo_batches(
    sku: str = Query(..., description="Target Product SKU"),
    warehouse_id: Optional[str] = Query(None, description="Warehouse ID filter"),
    required_qty: Optional[int] = Query(None, description="Required replenishment quantity"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns live batches in strict First-Expiry-First-Out (FEFO) priority from PostgreSQL.
    Excludes expired, quarantined, zero-quantity batches and inactive warehouses.
    """
    today = date(2026, 8, 24)
    query = (
        select(Batch, Product)
        .join(Product, Batch.sku == Product.sku)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(
            Warehouse.is_active != False,
            Batch.sku == sku,
            Batch.quantity > 0,
            Batch.expiry_date > today,
            Batch.is_quarantined == False
        )
    )
    if warehouse_id and warehouse_id != "All":
        query = query.where(Batch.warehouse_id == warehouse_id)

    query = query.order_by(Batch.expiry_date.asc())

    res = await db.execute(query)
    records = res.all()

    allocations = []
    remaining = required_qty or 1000
    for b, p in records:
        usable = b.available_quantity
        if usable <= 0:
            continue
        allocated = min(usable, remaining) if remaining > 0 else 0
        allocations.append({
            "batch_id": b.id,
            "sku": b.sku,
            "product_name": p.name,
            "warehouse_id": b.warehouse_id,
            "available_quantity": b.quantity,
            "expiry_date": b.expiry_date.strftime("%Y-%m-%d"),
            "days_to_expiry": (b.expiry_date - today).days,
            "allocated_quantity": allocated,
            "priority": len(allocations) + 1
        })
        if remaining > 0:
            remaining -= allocated

    return {
        "sku": sku,
        "warehouse_id": warehouse_id,
        "allocations": allocations
    }


@router.get("")
async def get_replenishment_overview(
    warehouse: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dynamically returns recommendations, transfer opportunities, supplier breakdowns,
    category splits, and purchase orders from the database.
    """
    today = date(2026, 8, 24)

    # 0. Discover active inter-DC FEFO transfer opportunities
    await NetworkBalancingEngine.identify_network_transfers(db)

    # 1. Dynamically synchronize recommendations with transfer-first policy
    await ReplenishmentEngine.sync_recommendations(db, warehouse_id=warehouse)
    await db.commit()

    # 1. Fetch Recommendations from DB (Active warehouses & PENDING status only for main recommendation list)
    rec_query = (
        select(ReplenishmentRecommendation, Product)
        .join(Product, ReplenishmentRecommendation.sku == Product.sku)
        .join(Warehouse, ReplenishmentRecommendation.warehouse_id == Warehouse.id)
        .where(
            Product.is_active != False,
            Warehouse.is_active != False,
            ReplenishmentRecommendation.status == "PENDING"
        )
    )
    if warehouse and warehouse != "All":
        rec_query = rec_query.where(ReplenishmentRecommendation.warehouse_id == warehouse)
    rec_query = rec_query.order_by(ReplenishmentRecommendation.created_at.desc())

    recs_res = await db.execute(rec_query)
    rec_records = recs_res.all()

    recommendations_list = []
    category_cost_map = {}
    supplier_spend_map = {}
    supplier_lead_map = {}

    for r, p in rec_records:
        cost_lakh = round(r.estimated_cost_inr / 100000.0, 1)
        category_cost_map[p.category] = category_cost_map.get(p.category, 0.0) + r.estimated_cost_inr
        
        supp = r.preferred_source or "HealthGen Pharma"
        supplier_spend_map[supp] = supplier_spend_map.get(supp, 0.0) + r.estimated_cost_inr
        supplier_lead_map[supp] = 5

        recommendations_list.append({
            "id": r.id,
            "priority": r.priority,
            "sku": r.sku,
            "name": p.name,
            "category": p.category,
            "warehouse": r.warehouse_id,
            "supplier": supp,
            "currentStock": r.current_stock,
            "forecastDemand": int(r.forecast_demand_30d) if r.forecast_demand_30d else int(r.recommended_quantity * 1.2),
            "recommendedQty": r.recommended_quantity,
            "recommendedFrequency": r.recommended_frequency,
            "nextReviewDate": r.next_review_date.strftime("%d %b %Y") if r.next_review_date else "28 Aug 2026",
            "decisionType": r.decision_type,
            "preferredSource": r.preferred_source,
            "estCost": f"₹{cost_lakh} L" if cost_lakh > 0 else "₹0",
            "status": r.status,
            "requestedBy": r.requested_by,
            "reasonWhat": r.reason_what,
            "reasonWhy": r.reason_why,
            "reasonWhen": r.reason_when,
            "reasonImpact": r.reason_impact
        })

    # 2. Transfer Opportunities from DB (Active warehouses only)
    active_wh_subquery = select(Warehouse.id).where(Warehouse.is_active != False)
    trf_query = (
        select(InventoryTransfer, Product)
        .join(Product, InventoryTransfer.sku == Product.sku)
        .where(
            Product.is_active != False,
            InventoryTransfer.source_warehouse_id.in_(active_wh_subquery),
            InventoryTransfer.destination_warehouse_id.in_(active_wh_subquery)
        )
    )
    if warehouse and warehouse != "All":
        trf_query = trf_query.where(
            (InventoryTransfer.source_warehouse_id == warehouse) | 
            (InventoryTransfer.destination_warehouse_id == warehouse)
        )
    trf_res = await db.execute(trf_query)
    trf_records = trf_res.all()

    transfers_list = [
        {
            "id": t.id,
            "sku": t.sku,
            "product": p.name,
            "from": t.source_warehouse_id,
            "to": t.destination_warehouse_id,
            "quantity": t.quantity,
            "cost": f"₹{round(getattr(t, 'estimated_transfer_cost_inr', t.quantity * 2.5) / 1000.0, 1)} K",
            "savings": f"₹{round(t.estimated_savings_inr / 100000.0, 2)} L",
            "reason": t.reason or "FEFO near-expiry transfer eliminates Tier-2 shortage",
            "status": t.status
        }
        for t, p in trf_records
    ]

    # 3. Dynamic Top Suppliers Breakdown from DB
    top_suppliers = []
    for s_name, s_spend in supplier_spend_map.items():
        s_cr = round(s_spend / 10000000.0, 2)
        top_suppliers.append({
            "name": s_name,
            "spend": f"₹{s_cr} Cr" if s_cr > 0 else f"₹{round(s_spend / 100000.0, 1)} L",
            "leadTime": f"{supplier_lead_map.get(s_name, 5)} days",
            "otif": "98.2%"
        })

    # 4. Dynamic Replenishment by Category from DB
    tot_rec_cost = sum(category_cost_map.values()) or 1.0
    replenishment_by_category = []
    for cat_name, cat_val in category_cost_map.items():
        pct = round((cat_val / tot_rec_cost) * 100)
        val_cr = round(cat_val / 10000000.0, 2)
        replenishment_by_category.append({
            "category": cat_name,
            "value": f"₹{val_cr} Cr" if val_cr > 0 else f"₹{round(cat_val / 100000.0, 1)} L",
            "pct": max(5, pct)
        })

    # 5. Purchase Orders & Requests from DB
    po_query = select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc())
    if warehouse and warehouse != "All":
        po_query = po_query.where(PurchaseOrder.warehouse_id == warehouse)
    po_res = await db.execute(po_query)
    all_pos = po_res.scalars().all()

    purchase_orders = [
        {
            "id": po.id,
            "supplier": po.supplier_name,
            "sku": po.sku,
            "warehouse": po.warehouse_id,
            "quantity": po.quantity,
            "value": f"₹{round(po.total_cost_inr / 100000.0, 1)} L",
            "date": po.order_date.strftime("%d %b %Y"),
            "status": po.status.capitalize()
        }
        for po in all_pos
    ]

    all_recs_query = (
        select(ReplenishmentRecommendation, Product)
        .join(Product, ReplenishmentRecommendation.sku == Product.sku)
        .join(Warehouse, ReplenishmentRecommendation.warehouse_id == Warehouse.id)
        .where(Product.is_active != False, Warehouse.is_active != False)
    )
    if warehouse and warehouse != "All":
        all_recs_query = all_recs_query.where(ReplenishmentRecommendation.warehouse_id == warehouse)
    all_recs_res = await db.execute(all_recs_query.order_by(ReplenishmentRecommendation.created_at.desc()))
    all_rec_records = all_recs_res.all()

    replenishment_requests = [
        {
            "id": f"RR-{r.sku}-{r.warehouse_id}",
            "sku": r.sku,
            "name": p.name if p else r.sku,
            "warehouse": r.warehouse_id,
            "qty": r.recommended_quantity,
            "requestedBy": r.requested_by or "Lead SCM Planner",
            "date": r.created_at.strftime("%d %b %Y") if r.created_at else "24 Aug 2026",
            "status": r.status.capitalize()
        }
        for r, p in all_rec_records
    ]

    approved_orders = [
        {
            "id": po.id,
            "name": f"PO for {po.sku}",
            "sku": po.sku,
            "warehouse": po.warehouse_id,
            "qty": po.quantity,
            "value": f"₹{round(po.total_cost_inr / 100000.0, 1)} L",
            "approvedOn": po.order_date.strftime("%d %b %Y"),
            "eta": po.eta_date.strftime("%d %b %Y") if po.eta_date else "27 Aug 2026",
            "status": po.status.capitalize()
        }
        for po in all_pos if po.status in ["APPROVED", "Approved", "SENT", "Sent", "Received", "COMPLETED", "Completed"]
    ]

    return {
        "recommendations": recommendations_list,
        "transfer_opportunities": transfers_list,
        "top_suppliers": top_suppliers,
        "replenishment_by_category": replenishment_by_category,
        "replenishment_requests": replenishment_requests,
        "approved_orders": approved_orders,
        "purchase_orders": purchase_orders
    }


@router.post("/{rec_id}/approve")
@router.post("/recommendations/{rec_id}/approve")
async def approve_recommendation(rec_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Approves a replenishment recommendation:
    - Updates recommendation status to 'APPROVED'
    - Creates corresponding PurchaseOrder or InventoryTransfer
    - Updates inbound stock in Inventory
    - Broadcasts live WebSocket event
    """
    rec_res = await db.execute(select(ReplenishmentRecommendation).where(ReplenishmentRecommendation.id == rec_id))
    rec = rec_res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Replenishment recommendation '{rec_id}' not found.")

    rec.status = "APPROVED"
    today = date(2026, 8, 24)

    po_id = None
    # If decision type is TRANSFER, update transfer records
    if rec.decision_type == "TRANSFER":
        trf_res = await db.execute(
            select(InventoryTransfer).where(
                InventoryTransfer.sku == rec.sku,
                InventoryTransfer.destination_warehouse_id == rec.warehouse_id,
                InventoryTransfer.status == "RECOMMENDED"
            )
        )
        trf = trf_res.scalars().first()
        if trf:
            trf.status = "APPROVED"
    else:
        # Create PurchaseOrder
        po_id = f"PO-{int(datetime.now(timezone.utc).timestamp())}"
        po = PurchaseOrder(
            id=po_id,
            sku=rec.sku,
            warehouse_id=rec.warehouse_id,
            supplier_name=rec.preferred_source or "HealthGen Pharma",
            quantity=rec.recommended_quantity,
            total_cost_inr=rec.estimated_cost_inr,
            order_date=today,
            eta_date=today + timedelta(days=5),
            status="APPROVED",
            created_at=datetime.now(timezone.utc)
        )
        db.add(po)

        # Increment inbound stock
        inv_res = await db.execute(
            select(Inventory).where(
                Inventory.sku == rec.sku,
                Inventory.warehouse_id == rec.warehouse_id
            )
        )
        inv = inv_res.scalars().first()
        if inv:
            inv.inbound_stock += rec.recommended_quantity
            inv.last_recalculated_at = datetime.now(timezone.utc)

    await db.commit()

    await ws_manager.broadcast({
        "event": "REPLENISHMENT_UPDATED",
        "action": "APPROVE",
        "id": rec.id,
        "sku": rec.sku,
        "warehouse_id": rec.warehouse_id
    })

    created_po_id = po_id if rec.decision_type != "TRANSFER" else None

    return {
        "success": True,
        "id": rec.id,
        "po_id": created_po_id,
        "status": "APPROVED",
        "message": f"Replenishment recommendation for {rec.sku} at {rec.warehouse_id} approved. Purchase Order created."
    }


@router.post("/{rec_id}/reject")
async def reject_recommendation(rec_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Rejects a replenishment recommendation in the database.
    """
    rec_res = await db.execute(select(ReplenishmentRecommendation).where(ReplenishmentRecommendation.id == rec_id))
    rec = rec_res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Replenishment recommendation '{rec_id}' not found.")

    rec.status = "REJECTED"
    await db.commit()

    await ws_manager.broadcast({
        "event": "REPLENISHMENT_UPDATED",
        "action": "REJECT",
        "id": rec.id,
        "sku": rec.sku
    })

    return {
        "success": True,
        "id": rec.id,
        "status": "REJECTED",
        "message": f"Recommendation {rec.id} rejected."
    }

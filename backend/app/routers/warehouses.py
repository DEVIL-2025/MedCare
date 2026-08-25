from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta, timezone
from pydantic import BaseModel, Field

from backend.app.database import get_db
from backend.app.models.warehouse import Warehouse
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.transaction import InventoryTransaction
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.replenishment import ReplenishmentRecommendation
from backend.app.models.alert import Alert
from backend.app.schemas.warehouse import WarehouseCreate
from backend.app.routers.ws import ws_manager

router = APIRouter(prefix="/api/warehouses", tags=["Warehouses"])


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    tier: Optional[str] = None
    region: Optional[str] = None
    capacity_units: Optional[int] = None
    status: Optional[str] = None


@router.get("")
async def get_warehouses_overview(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns dynamically aggregated DC capacity metrics, space utilization,
    inventory valuation rankings, capacity utilization trends, and geographical map points.
    """
    today = date.today()
    res = await db.execute(
        select(Warehouse).where(Warehouse.is_active != False).order_by(Warehouse.id.asc())
    )
    warehouses = res.scalars().all()

    inv_res = await db.execute(
        select(Inventory, Product).join(Product, Inventory.sku == Product.sku)
        .where(Product.is_active != False)
    )
    all_inv_items = inv_res.all()

    wh_inv_map = {}
    wh_crit_map = {}
    wh_val_map = {}

    for inv, prod in all_inv_items:
        wh_inv_map[inv.warehouse_id] = wh_inv_map.get(inv.warehouse_id, 0) + inv.current_stock
        wh_val_map[inv.warehouse_id] = wh_val_map.get(inv.warehouse_id, 0.0) + (inv.current_stock * prod.unit_cost)
        if inv.risk_level == "critical" or inv.status in ["CRITICAL", "OUT_OF_STOCK"]:
            wh_crit_map[inv.warehouse_id] = wh_crit_map.get(inv.warehouse_id, 0) + 1

    overview = []
    map_points = []
    top_by_value = []

    max_wh_val = max(wh_val_map.values()) if wh_val_map else 5000000.0

    for w in warehouses:
        inv_units = wh_inv_map.get(w.id, 0)
        crit_count = wh_crit_map.get(w.id, 0)
        wh_val_inr = wh_val_map.get(w.id, 0.0)
        val_str = f"₹{wh_val_inr / 10000000.0:.2f} Cr" if wh_val_inr >= 10000000 else f"₹{wh_val_inr / 100000.0:.2f} Lakhs"

        # Dynamic utilization calculation
        utilization_pct = min(100, int((inv_units / max(1, w.capacity_units)) * 100)) if w.capacity_units else int(w.current_utilization_pct)
        if utilization_pct == 0 and inv_units > 0:
            utilization_pct = int(w.current_utilization_pct)

        status_str = w.status or ("At Risk" if (crit_count >= 2 or utilization_pct >= 85) else ("Monitor" if crit_count >= 1 else "Healthy"))

        cap_display = f"{w.capacity_units:,} units" if w.capacity_units < 100000 else f"{w.capacity_units // 100000} Lakh units"

        overview.append({
            "id": w.id,
            "name": w.name,
            "location": w.location,
            "tier": w.tier,
            "region": w.region,
            "capacity": cap_display,
            "capacityUnits": w.capacity_units,
            "inventory": int(inv_units),
            "utilization": utilization_pct,
            "criticalSkus": crit_count,
            "health": w.health_score,
            "status": status_str,
            "valInr": wh_val_inr,
            "valDisplay": val_str
        })

        map_points.append({
            "id": w.id,
            "x": w.map_x,
            "y": w.map_y,
            "status": status_str
        })

        pct_of_max = min(100, int((wh_val_inr / max(1.0, max_wh_val)) * 100))
        top_by_value.append({
            "id": w.id,
            "name": w.name,
            "value": val_str,
            "valInr": wh_val_inr,
            "pct": max(15, pct_of_max)
        })

    top_by_value.sort(key=lambda x: x["valInr"], reverse=True)

    # Dynamic Historical Capacity Trend from Inventory Transactions
    top_3_wh_ids = [w.id for w in warehouses[:3]]

    capacity_trend = []

    for weeks_ago in range(5, -1, -1):
        target_date = today - timedelta(days=weeks_ago * 7)

        # End-of-day boundary for the target date
        target_datetime = datetime.combine(
            target_date,
            datetime.max.time()
        )

        point_data: Dict[str, Any] = {
            "date": target_date.strftime("%d %b")
        }

        for wh in warehouses[:3]:

            # Get the latest inventory transaction for this warehouse
            # on or before the historical date.
            historical_res = await db.execute(
                select(InventoryTransaction)
                .where(
                    and_(
                        InventoryTransaction.warehouse_id == wh.id,
                        InventoryTransaction.timestamp <= target_datetime
                    )
                )
                .order_by(
                    InventoryTransaction.timestamp.desc(),
                    InventoryTransaction.id.desc()
                )
                .limit(1)
            )

            historical_transaction = historical_res.scalars().first()

            if historical_transaction:
                historical_stock = historical_transaction.new_stock

                historical_utilization = (
                    historical_stock / max(1, wh.capacity_units)
                ) * 100

                point_data[wh.id] = round(
                    min(100, max(0, historical_utilization)),
                    1
                )

            else:
                # No transaction history exists for this warehouse/date.
                # Do not fabricate a value.
                point_data[wh.id] = 0

        capacity_trend.append(point_data)

    colors = ["#177A5B", "#1E9270", "#D5A72C", "#68716D", "#3B82F6"]
    inventory_distribution = [
        {
            "name": item["id"],
            "value": item["inventory"],
            "color": colors[idx % len(colors)]
        }
        for idx, item in enumerate(overview) if item["inventory"] > 0
    ]

    return {
        "overview": overview,
        "map_points": map_points,
        "top_by_value": top_by_value,
        "capacity_trend": capacity_trend,
        "inventory_distribution": inventory_distribution,
        "metrics": {
            "total_warehouses": len(warehouses),
            "total_capacity": sum(w.capacity_units for w in warehouses),
            "avg_utilization": round(sum(o["utilization"] for o in overview) / max(1, len(overview)), 1) if overview else 0.0,
            "average_utilization": round(sum(o["utilization"] for o in overview) / max(1, len(overview)), 1) if overview else 0.0,
            "total_inventory_value": f"₹{sum(o.get('valInr', 0.0) for o in overview) / 100000.0:.2f} Lakhs",
            "at_risk_warehouses": len([o for o in overview if o["status"] == "At Risk"])
        },
        "kpis": {
            "total_warehouses": len(warehouses),
            "total_capacity": sum(w.capacity_units for w in warehouses),
            "avg_utilization": round(sum(o["utilization"] for o in overview) / max(1, len(overview)), 1) if overview else 0.0,
            "average_utilization": round(sum(o["utilization"] for o in overview) / max(1, len(overview)), 1) if overview else 0.0,
            "total_inventory_value": f"₹{sum(o.get('valInr', 0.0) for o in overview) / 100000.0:.2f} Lakhs",
            "at_risk_warehouses": len([o for o in overview if o["status"] == "At Risk"])
        }
    }


@router.post("")
async def add_warehouse(payload: WarehouseCreate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Adds a new warehouse distribution center or reactivates a decommissioned one."""
    wh_id = payload.id.strip().upper()
    existing_res = await db.execute(select(Warehouse).where(Warehouse.id == wh_id))
    existing_wh = existing_res.scalars().first()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if existing_wh:
        if existing_wh.is_active:
            raise HTTPException(status_code=400, detail=f"Warehouse ID '{wh_id}' already exists.")
        else:
            # Reactivate decommissioned warehouse
            existing_wh.is_active = True
            existing_wh.name = payload.name.strip()
            existing_wh.location = payload.location.strip()
            existing_wh.tier = payload.tier or "Tier-1 DC"
            existing_wh.region = payload.region or "South"
            existing_wh.capacity_units = payload.capacity_units or 10000
            existing_wh.current_utilization_pct = payload.current_utilization_pct or 10.0
            existing_wh.health_score = 85
            existing_wh.status = "Healthy"
            existing_wh.map_x = payload.map_x or 50.0
            existing_wh.map_y = payload.map_y or 50.0
            new_wh = existing_wh
    else:
        new_wh = Warehouse(
            id=wh_id,
            name=payload.name.strip(),
            location=payload.location.strip(),
            tier=payload.tier or "Tier-1 DC",
            region=payload.region or "South",
            capacity_units=payload.capacity_units or 10000,
            current_utilization_pct=payload.current_utilization_pct or 10.0,
            health_score=85,
            status="Healthy",
            is_active=True,
            map_x=payload.map_x or 50.0,
            map_y=payload.map_y or 50.0,
            created_at=now_utc
        )
        db.add(new_wh)

    await db.flush()

    # Initialize or ensure inventory records for all active products
    prod_res = await db.execute(select(Product).where(Product.is_active != False))
    all_prods = prod_res.scalars().all()

    for p in all_prods:
        inv_res = await db.execute(
            select(Inventory).where(
                Inventory.sku == p.sku,
                Inventory.warehouse_id == new_wh.id
            )
        )
        existing_inv = inv_res.scalars().first()
        if not existing_inv:
            inv = Inventory(
                sku=p.sku,
                warehouse_id=new_wh.id,
                current_stock=0,
                reserved_stock=0,
                inbound_stock=0,
                reorder_point=p.default_reorder_point,
                safety_stock=p.default_safety_stock,
                status="OUT_OF_STOCK",
                risk_level="critical",
                days_of_cover=0.0,
                last_recalculated_at=now_utc
            )
            db.add(inv)

    await db.commit()

    # Broadcast WebSocket update
    await ws_manager.broadcast({
        "event": "WAREHOUSE_CREATED",
        "warehouse_id": new_wh.id,
        "name": new_wh.name
    })

    return {
        "success": True,
        "warehouse": {
            "id": new_wh.id,
            "name": new_wh.name,
            "location": new_wh.location
        },
        "message": f"Warehouse '{new_wh.name}' ({new_wh.id}) commissioned successfully."
    }


@router.put("/{id}")
async def update_warehouse(id: str, payload: WarehouseUpdate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Updates existing warehouse parameters."""
    res = await db.execute(select(Warehouse).where(Warehouse.id == id))
    wh = res.scalars().first()
    if not wh:
        raise HTTPException(status_code=404, detail=f"Warehouse '{id}' not found.")

    if payload.name is not None:
        wh.name = payload.name.strip()
    if payload.location is not None:
        wh.location = payload.location.strip()
    if payload.tier is not None:
        wh.tier = payload.tier.strip()
    if payload.region is not None:
        wh.region = payload.region.strip()
    if payload.capacity_units is not None:
        wh.capacity_units = payload.capacity_units
    if payload.status is not None:
        wh.status = payload.status.strip()

    await db.commit()

    await ws_manager.broadcast({
        "event": "WAREHOUSE_UPDATED",
        "warehouse_id": wh.id,
        "name": wh.name
    })

    return {
        "success": True,
        "warehouse_id": wh.id,
        "message": f"Warehouse '{wh.name}' ({wh.id}) updated successfully."
    }


@router.delete("/{id}")
async def delete_warehouse(id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Decommissions (soft-deletes) a warehouse and cascades invalidation to pending actions."""
    res = await db.execute(select(Warehouse).where(Warehouse.id == id))
    wh = res.scalars().first()
    if not wh:
        raise HTTPException(status_code=404, detail=f"Warehouse '{id}' not found.")

    wh.is_active = False
    wh.status = "Decommissioned"

    # Invalidate / cancel pending recommended transfers referencing this warehouse
    trfs_res = await db.execute(
        select(InventoryTransfer).where(
            or_(
                InventoryTransfer.source_warehouse_id == id,
                InventoryTransfer.destination_warehouse_id == id
            ),
            InventoryTransfer.status == "RECOMMENDED"
        )
    )
    for t in trfs_res.scalars().all():
        t.status = "CANCELLED"

    # Invalidate / cancel pending replenishment recommendations for this warehouse
    recs_res = await db.execute(
        select(ReplenishmentRecommendation).where(
            ReplenishmentRecommendation.warehouse_id == id,
            ReplenishmentRecommendation.status == "PENDING"
        )
    )
    for r in recs_res.scalars().all():
        r.status = "CANCELLED"

    # Invalidate active alerts for this warehouse
    alerts_res = await db.execute(
        select(Alert).where(Alert.warehouse_id == id, Alert.status != "Resolved")
    )
    for a in alerts_res.scalars().all():
        a.status = "Resolved"

    await db.commit()

    await ws_manager.broadcast({
        "event": "WAREHOUSE_DECOMMISSIONED",
        "warehouse_id": wh.id,
        "name": wh.name
    })

    return {
        "success": True,
        "warehouse_id": wh.id,
        "message": f"Warehouse '{wh.name}' ({wh.id}) decommissioned successfully."
    }

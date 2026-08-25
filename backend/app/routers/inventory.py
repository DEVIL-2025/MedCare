from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timezone

from backend.app.database import get_db
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.models.sales import SalesOrder
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.replenishment import ReplenishmentRecommendation, PurchaseOrder
from backend.app.models.alert import Alert
from backend.app.models.transaction import InventoryTransaction
from backend.app.models.notification import NotificationLog
from backend.app.models.escalation import AlertEscalation
from backend.app.models.risk import InventoryRisk
from backend.app.models.forecast import ForecastRecord, DemandSurgeEvent
from backend.app.models.signal import DemandSignal
from backend.app.models.demand import DemandHistory, Promotion, DistributorOrder
from backend.app.ml.predict import PredictionService
from backend.app.schemas.inventory import ProductCreate, ProductResponse, SaleCreate
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.expiry_fefo_engine import ExpiryFEFOEngine
from backend.app.engines.risk_engine import RiskEngine
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.routers.ws import ws_manager
from backend.app.dependencies.auth import require_permission, get_optional_user
from backend.app.models.auth import User
from backend.app.utils.timezone import get_today_ist, get_now_ist, format_ist_datetime, format_ist_date

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get("")
async def get_inventory(
    warehouse: Optional[str] = "All",
    category: Optional[str] = "All",
    search: Optional[str] = "",
    quick_filter: Optional[str] = "all",  # all, low, out, expiring, slow, overstock
    rollup: Optional[bool] = False,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Returns inventory items with product master metadata, thresholds, status, and live per-batch expiry.
    When warehouse == 'All' and rollup is True, aggregates inventory by SKU and embeds per-DC breakdown.
    """
    today = get_today_ist()

    query = (
        select(Inventory, Product)
        .join(Product, Inventory.sku == Product.sku)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .where(Product.is_active != False, Warehouse.is_active != False)
    )

    if warehouse and warehouse != "All":
        query = query.where(Inventory.warehouse_id == warehouse)
    if category and category != "All":
        query = query.where(Product.category == category)

    res = await db.execute(query)
    items = res.all()

    # Dynamic status & risk evaluation ensuring direct DB changes reflect instantly
    for inv, prod in items:
        dyn_status, dyn_risk = InventoryEngine.evaluate_inventory_status(
            inv.current_stock, inv.reorder_point, inv.safety_stock
        )
        inv.status = dyn_status
        inv.risk_level = dyn_risk

    # Pre-fetch all active batches per SKU and per SKU-warehouse (active warehouses only)
    batches_res = await db.execute(
        select(Batch)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(Warehouse.is_active != False, Batch.quantity > 0)
        .order_by(Batch.expiry_date.asc())
    )
    all_batches = batches_res.scalars().all()
    batch_map = {}
    sku_wh_batches: Dict[str, List[Dict[str, Any]]] = {}
    sku_all_batches: Dict[str, List[Dict[str, Any]]] = {}

    for b in all_batches:
        key = f"{b.sku}_{b.warehouse_id}"
        if key not in batch_map:
            batch_map[key] = b
        if b.sku not in batch_map:
            batch_map[b.sku] = b

        b_dict = {
            "id": b.id,
            "batchId": b.id,
            "warehouseId": b.warehouse_id,
            "quantity": b.quantity,
            "reservedQuantity": b.reserved_quantity,
            "availableQuantity": b.available_quantity,
            "expiryDate": b.expiry_date.strftime("%Y-%m-%d"),
            "daysToExpiry": (b.expiry_date - today).days,
            "status": b.status
        }
        sku_wh_batches.setdefault(key, []).append(b_dict)
        sku_all_batches.setdefault(b.sku, []).append(b_dict)

    search_lower = search.lower().strip() if search else ""

    if warehouse == "All" and rollup:
        # Group and aggregate by SKU across all warehouses
        sku_groups: Dict[str, Dict[str, Any]] = {}
        for inv, prod in items:
            if search_lower and (search_lower not in prod.name.lower() and search_lower not in prod.sku.lower()):
                continue

            earliest_batch = batch_map.get(f"{inv.sku}_{inv.warehouse_id}")
            days_to_exp = (earliest_batch.expiry_date - today).days if earliest_batch else 999

            if prod.sku not in sku_groups:
                sku_groups[prod.sku] = {
                    "sku": prod.sku,
                    "name": prod.name,
                    "category": prod.category,
                    "warehouse": "Network Rollup",
                    "warehouse_id": None,
                    "currentStock": 0,
                    "reservedStock": 0,
                    "inboundStock": 0,
                    "availableStock": 0,
                    "reorderPoint": 0,
                    "safetyStock": 0,
                    "unitCost": prod.unit_cost,
                    "moq": prod.moq,
                    "unit": prod.unit,
                    "minDaysCover": 999.0,
                    "earliestExpiryDays": 999,
                    "earliestExpiryDate": "-",
                    "hasCritical": False,
                    "hasLowStock": False,
                    "warehouseBreakdown": []
                }

            group = sku_groups[prod.sku]
            group["currentStock"] += inv.current_stock
            group["reservedStock"] += inv.reserved_stock
            group["inboundStock"] += inv.inbound_stock
            group["availableStock"] += inv.available_stock
            group["reorderPoint"] += inv.reorder_point
            group["safetyStock"] += inv.safety_stock
            group["minDaysCover"] = min(group["minDaysCover"], inv.days_of_cover or 0.0)

            if days_to_exp < group["earliestExpiryDays"]:
                group["earliestExpiryDays"] = days_to_exp
                group["earliestExpiryDate"] = earliest_batch.expiry_date.strftime("%Y-%m-%d") if earliest_batch else "-"

            if inv.status in ["CRITICAL", "OUT_OF_STOCK"]:
                group["hasCritical"] = True
            elif inv.status == "LOW_STOCK":
                group["hasLowStock"] = True

            dc_batches = sku_wh_batches.get(f"{inv.sku}_{inv.warehouse_id}", [])
            group["warehouseBreakdown"].append({
                "warehouseId": inv.warehouse_id,
                "currentStock": inv.current_stock,
                "reservedStock": inv.reserved_stock,
                "availableStock": inv.available_stock,
                "reorderPoint": inv.reorder_point,
                "daysOfCover": inv.days_of_cover,
                "status": inv.status.replace("_", " ").title(),
                "risk": inv.risk_level,
                "earliestExpiry": earliest_batch.expiry_date.strftime("%Y-%m-%d") if earliest_batch else "-",
                "daysToExpiry": days_to_exp,
                "batches": dc_batches
            })

        results = []
        for sku, group in sku_groups.items():
            status = "Critical" if group["hasCritical"] else ("Low Stock" if group["hasLowStock"] else "Healthy")
            risk = "critical" if group["hasCritical"] else ("high" if group["hasLowStock"] else "low")
            
            # Quick filters
            if quick_filter == "low" and not group["hasLowStock"]:
                continue
            elif quick_filter == "out" and group["currentStock"] > 0:
                continue
            elif quick_filter == "expiring" and group["earliestExpiryDays"] > 60:
                continue
            elif quick_filter in ["slow", "overstock"] and not (group["currentStock"] > group["reorderPoint"] * 1.8 or status == "OVERSTOCK"):
                continue

            results.append({
                "sku": group["sku"],
                "name": group["name"],
                "category": group["category"],
                "warehouse": "Network Rollup",
                "warehouse_id": None,
                "currentStock": group["currentStock"],
                "reservedStock": group["reservedStock"],
                "inboundStock": group["inboundStock"],
                "availableStock": group["availableStock"],
                "reorderPoint": group["reorderPoint"],
                "safetyStock": group["safetyStock"],
                "daysOfCover": round(group["minDaysCover"], 1) if group["minDaysCover"] != 999.0 else 30.0,
                "expiry": group["earliestExpiryDate"],
                "daysToExpiry": group["earliestExpiryDays"] if group["earliestExpiryDays"] != 999 else 180,
                "risk": risk,
                "status": status,
                "unitCost": group["unitCost"],
                "moq": group["moq"],
                "unit": group["unit"],
                "warehouseBreakdown": group["warehouseBreakdown"],
                "batches": sku_all_batches.get(group["sku"], [])
            })
        return results

    # Single-DC or standard view
    results = []
    for inv, prod in items:
        if search_lower and (search_lower not in prod.name.lower() and search_lower not in prod.sku.lower()):
            continue

        earliest_batch = batch_map.get(f"{inv.sku}_{inv.warehouse_id}")
        expiry_str = earliest_batch.expiry_date.strftime("%Y-%m-%d") if earliest_batch else "-"
        days_to_exp = (earliest_batch.expiry_date - today).days if earliest_batch else 999

        # Quick filters
        if quick_filter == "low" and inv.status != "LOW_STOCK":
            continue
        elif quick_filter == "out" and inv.status != "OUT_OF_STOCK":
            continue
        elif quick_filter == "expiring" and days_to_exp > 60:
            continue
        elif quick_filter in ["slow", "overstock"] and not (inv.current_stock > inv.reorder_point * 1.8 or inv.status == "OVERSTOCK"):
            continue

        dc_batches = sku_wh_batches.get(f"{inv.sku}_{inv.warehouse_id}", [])
        results.append({
            "sku": prod.sku,
            "name": prod.name,
            "category": prod.category,
            "warehouse": inv.warehouse_id,
            "currentStock": inv.current_stock,
            "reservedStock": inv.reserved_stock,
            "inboundStock": inv.inbound_stock,
            "availableStock": inv.available_stock,
            "reorderPoint": inv.reorder_point,
            "safetyStock": inv.safety_stock,
            "daysOfCover": inv.days_of_cover,
            "expiry": expiry_str,
            "daysToExpiry": days_to_exp,
            "risk": inv.risk_level,
            "status": inv.status.replace("_", " ").title(),
            "unitCost": prod.unit_cost,
            "moq": prod.moq,
            "unit": prod.unit,
            "batches": dc_batches
        })

    return results


@router.get("/products")
async def get_products(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns all active product master catalog items."""
    res = await db.execute(
        select(Product).where(Product.is_active != False).order_by(Product.name.asc())
    )
    prods = res.scalars().all()
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "criticality": p.criticality,
            "unit": p.unit,
            "shelfLifeDays": p.shelf_life_days,
            "defaultReorderPoint": p.default_reorder_point,
            "defaultSafetyStock": p.default_safety_stock,
            "moq": p.moq,
            "unitCost": p.unit_cost,
            "isTemperatureSensitive": p.is_temperature_sensitive
        }
        for p in prods
    ]


@router.delete("/products/{sku}")
async def delete_product(
    sku: str,
    current_user: User = Depends(require_permission("inventory.delete_product")),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Permanently deletes a product from the database and cascades deletion to all
    dependent rows across inventory, batches, transactions, transfers, alerts, and forecasts (Admin Only).
    """
    res = await db.execute(select(Product).where(Product.sku == sku))
    prod = res.scalars().first()
    if not prod:
        raise HTTPException(status_code=404, detail=f"Product with SKU '{sku}' not found in database.")

    prod_name = prod.name

    # 1. Delete dependent alerts & notification logs / escalations
    alert_ids_res = await db.execute(select(Alert.id).where(Alert.sku == sku))
    alert_ids = alert_ids_res.scalars().all()
    if alert_ids:
        await db.execute(delete(NotificationLog).where(NotificationLog.alert_id.in_(alert_ids)))
        await db.execute(delete(AlertEscalation).where(AlertEscalation.alert_id.in_(alert_ids)))
        await db.execute(delete(Alert).where(Alert.id.in_(alert_ids)))

    # 2. Delete transfers, purchase orders, replenishment recs
    await db.execute(delete(InventoryTransfer).where(InventoryTransfer.sku == sku))
    await db.execute(delete(PurchaseOrder).where(PurchaseOrder.sku == sku))
    await db.execute(delete(ReplenishmentRecommendation).where(ReplenishmentRecommendation.sku == sku))

    # 3. Delete risk & forecasting artifacts
    await db.execute(delete(InventoryRisk).where(InventoryRisk.sku == sku))
    await db.execute(delete(DemandSurgeEvent).where(DemandSurgeEvent.sku == sku))
    await db.execute(delete(ForecastRecord).where(ForecastRecord.sku == sku))
    await db.execute(delete(DemandSignal).where(DemandSignal.sku == sku))
    await db.execute(delete(Promotion).where(Promotion.sku == sku))

    # 4. Delete demand history, distributor orders, sales orders, transactions, batches, inventory
    await db.execute(delete(DistributorOrder).where(DistributorOrder.sku == sku))
    await db.execute(delete(DemandHistory).where(DemandHistory.sku == sku))
    await db.execute(delete(SalesOrder).where(SalesOrder.sku == sku))
    await db.execute(delete(InventoryTransaction).where(InventoryTransaction.sku == sku))
    await db.execute(delete(Batch).where(Batch.sku == sku))
    await db.execute(delete(Inventory).where(Inventory.sku == sku))

    # 5. Delete product master record
    await db.execute(delete(Product).where(Product.sku == sku))

    # Recalculate recommendations & transfers
    await NetworkBalancingEngine.identify_network_transfers(db)
    await ReplenishmentEngine.sync_recommendations(db)

    await db.commit()

    # Clear ML prediction cache
    PredictionService.invalidate_cache()

    # Broadcast WebSocket update
    await ws_manager.broadcast({
        "event": "PRODUCT_DELETED",
        "sku": sku,
        "name": prod_name,
        "message": f"Product '{prod_name}' ({sku}) has been deleted from the database."
    })
    await ws_manager.broadcast({
        "event": "REPLENISHMENT_UPDATED",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {
        "success": True,
        "sku": sku,
        "message": f"Product '{prod_name}' ({sku}) deleted successfully from database."
    }


@router.post("/products")
async def add_product(payload: ProductCreate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Inserts a new product into the database and initializes inventory records across warehouses.
    """
    existing_res = await db.execute(select(Product).where(Product.sku == payload.sku))
    if existing_res.scalars().first():
        raise HTTPException(status_code=400, detail=f"Product with SKU '{payload.sku}' already exists.")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    new_prod = Product(
        sku=payload.sku.strip().upper(),
        name=payload.name.strip(),
        category=payload.category.strip(),
        criticality=payload.criticality or "Medium",
        unit=payload.unit or "Units",
        shelf_life_days=payload.shelf_life_days or 730,
        default_reorder_point=payload.default_reorder_point or 200,
        default_safety_stock=payload.default_safety_stock or 80,
        moq=payload.moq or 50,
        unit_cost=payload.unit_cost or 50.0,
        is_temperature_sensitive=payload.is_temperature_sensitive or False,
        created_at=now_utc
    )
    db.add(new_prod)
    await db.flush()

    # Initialize inventory records across active warehouses
    wh_res = await db.execute(select(Warehouse).where(Warehouse.is_active != False))
    all_whs = wh_res.scalars().all()
    today = get_today_ist()

    for w in all_whs:
        initial_qty = (
            payload.initial_stock
            if payload.initial_warehouse_id == w.id and payload.initial_stock is not None
            else 0
        )
        inv_status, risk_level = InventoryEngine.evaluate_inventory_status(
            initial_qty,
            new_prod.default_reorder_point,
            new_prod.default_safety_stock
        )
        inv = Inventory(
            sku=new_prod.sku,
            warehouse_id=w.id,
            current_stock=initial_qty,
            reserved_stock=0,
            inbound_stock=0,
            reorder_point=new_prod.default_reorder_point,
            safety_stock=new_prod.default_safety_stock,
            status=inv_status,
            risk_level=risk_level,
            days_of_cover=round((initial_qty / max(1, new_prod.default_reorder_point / 20.0)), 1) if initial_qty > 0 else 0.0,
            last_recalculated_at=now_utc
        )
        db.add(inv)

        if initial_qty > 0:
            batch_id = f"BAT-{new_prod.sku}-{w.id}-INIT"
            batch = Batch(
                id=batch_id,
                sku=new_prod.sku,
                warehouse_id=w.id,
                quantity=initial_qty,
                reserved_quantity=0,
                mfg_date=today,
                expiry_date=today.replace(year=today.year + (new_prod.shelf_life_days // 365 or 2)),
                status="ACTIVE"
            )
            db.add(batch)

    # Recalculate recommendations & transfers
    await NetworkBalancingEngine.identify_network_transfers(db)
    await ReplenishmentEngine.sync_recommendations(db)

    await db.commit()

    # Broadcast event
    await ws_manager.broadcast({
        "event": "PRODUCT_CREATED",
        "sku": new_prod.sku,
        "name": new_prod.name,
        "category": new_prod.category
    })
    await ws_manager.broadcast({
        "event": "REPLENISHMENT_UPDATED",
        "timestamp": now_utc.isoformat()
    })

    return {
        "success": True,
        "sku": new_prod.sku,
        "name": new_prod.name,
        "message": f"Product '{new_prod.name}' ({new_prod.sku}) successfully registered in database catalog."
    }


@router.post("/sales")
async def record_sale(payload: SaleCreate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Executes real-time sale transaction:
    1. Records sales_order in database
    2. Atomically decrements inventory stock and batch quantities (via FEFO)
    3. Logs inventory_transaction (type: SALE)
    4. Evaluates thresholds and triggers alerts if low/out of stock
    5. Recalculates transfers & replenishment recommendations
    6. Broadcasts live WebSocket event
    """
    prod_res = await db.execute(select(Product).where(Product.sku == payload.sku))
    prod = prod_res.scalars().first()
    if not prod:
        raise HTTPException(status_code=404, detail=f"Product with SKU '{payload.sku}' not found.")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    order_num = f"ORD-{int(now_utc.timestamp())}"

    try:
        # Deduct stock via inventory engine
        tx, inv = await InventoryEngine.process_transaction(
            session=db,
            transaction_type="SALE",
            sku=payload.sku,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            reference_id=order_num,
            reason=payload.reason or f"Hospital / Distributor Sale to {payload.customer_name}",
            performed_by="Sales Dispatch"
        )

        # Compute pricing
        unit_price = float(payload.unit_price) if payload.unit_price is not None else float(prod.unit_cost * 1.25)
        total_price = round(unit_price * payload.quantity, 2)

        # Create SalesOrder record
        sale_order = SalesOrder(
            id=f"SO-{int(now_utc.timestamp())}",
            order_number=order_num,
            sku=payload.sku,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            unit_price=unit_price,
            total_price=total_price,
            customer_name=payload.customer_name,
            channel=payload.channel or "Hospital",
            status="COMPLETED",
            created_at=now_utc
        )
        db.add(sale_order)

        # Recalculate Risk & Synchronize alerts dynamically
        await RiskEngine.evaluate_inventory_risk(db, payload.sku, payload.warehouse_id)
        await AlertEscalationEngine.sync_inventory_alerts(db, sku=payload.sku, warehouse_id=payload.warehouse_id)
        await NetworkBalancingEngine.identify_network_transfers(db)
        await ReplenishmentEngine.sync_recommendations(db)

        await db.commit()

        # Broadcast live event
        await ws_manager.broadcast({
            "event": "INVENTORY_TRANSACTION",
            "transaction_type": "SALE",
            "sku": payload.sku,
            "warehouse_id": payload.warehouse_id,
            "quantity": payload.quantity,
            "new_stock": inv.current_stock,
            "order_number": order_num,
            "customer": payload.customer_name
        })
        await ws_manager.broadcast({
            "event": "REPLENISHMENT_UPDATED",
            "timestamp": now_utc.isoformat()
        })

        return {
            "success": True,
            "order_number": order_num,
            "sku": payload.sku,
            "warehouse_id": payload.warehouse_id,
            "quantity_sold": payload.quantity,
            "remaining_stock": inv.current_stock,
            "total_price": total_price,
            "message": f"Sale of {payload.quantity:,} units for {prod.name} recorded. Inventory updated."
        }

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record sale: {str(e)}")


@router.get("/batches")
async def get_batches(
    sku: Optional[str] = None,
    warehouse: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns batch-level expiry details with FEFO categorization."""
    today = get_today_ist()
    query = select(Batch, Product).join(Product, Batch.sku == Product.sku).where(Batch.quantity > 0)

    if sku:
        query = query.where(Batch.sku == sku)
    if warehouse and warehouse != "All":
        query = query.where(Batch.warehouse_id == warehouse)

    query = query.order_by(Batch.expiry_date.asc())
    res = await db.execute(query)
    records = res.all()

    results = []
    for b, p in records:
        cat, days = ExpiryFEFOEngine.categorize_batch_expiry(b.expiry_date, today)
        results.append({
            "id": b.id,
            "sku": b.sku,
            "name": p.name,
            "warehouse": b.warehouse_id,
            "quantity": b.quantity,
            "reservedQuantity": b.reserved_quantity,
            "mfgDate": b.mfg_date.strftime("%Y-%m-%d"),
            "expiryDate": b.expiry_date.strftime("%Y-%m-%d"),
            "daysToExpiry": days,
            "expiryCategory": cat,
            "status": b.status,
            "isQuarantined": b.is_quarantined
        })

    return results


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)) -> List[str]:
    """Returns list of distinct pharmaceutical product categories."""
    res = await db.execute(select(Product.category).distinct())
    return [c[0] for c in res.all()]

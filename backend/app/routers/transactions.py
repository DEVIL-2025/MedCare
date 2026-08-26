from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, cast, String
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.schemas.transaction import TransactionCreate, TransactionResponse
from backend.app.models.transaction import InventoryTransaction
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.transfer import InventoryTransfer
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.risk_engine import RiskEngine
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.services.notification_service import NotificationService
from backend.app.services.email_alert_service import trigger_async_low_stock_check
from backend.app.routers.ws import ws_manager
from backend.app.utils.timezone import get_utc_now, format_ist_datetime, to_ist_iso, get_now_ist

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("", response_model=Dict[str, Any])
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes an atomic inventory transaction (SALE, CONSUMPTION, RECEIPT, ADJUSTMENT, TRANSFER).
    For Inter-DC Transfers:
    - Atomically decrements source warehouse stock and batch
    - Atomically increments destination warehouse stock and batch
    - Recalculates inventory risk on both source and destination
    - Synchronizes alerts and recommended transfers
    - Broadcasts live WebSocket event
    """
    try:
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        tx_type_upper = payload.transaction_type.strip().upper()
        has_dest_wh = payload.destination_warehouse_id and payload.destination_warehouse_id.strip() != ""
        is_transfer = (tx_type_upper in ["TRANSFER", "TRANSFER_OUT", "INTER_DC_TRANSFER"] and has_dest_wh) or (tx_type_upper == "TRANSFER")

        if is_transfer:
            src_wh = payload.warehouse_id.strip().upper()
            dest_wh = (payload.destination_warehouse_id or "").strip().upper()
            if not dest_wh or dest_wh == src_wh:
                raise ValueError("Destination warehouse is required and must be different from source warehouse for Inter-DC transfers.")

            ref_id = payload.reference_id or f"TRF-{payload.sku.upper()}-{src_wh}-{dest_wh}"

            # 1. Deduct from source warehouse atomically
            tx_out, inv_src = await InventoryEngine.process_transaction(
                session=db,
                transaction_type="TRANSFER_OUT",
                sku=payload.sku,
                warehouse_id=src_wh,
                quantity=payload.quantity,
                batch_id=payload.batch_id,
                reference_id=ref_id,
                reason=payload.reason or f"Inter-DC Transfer to {dest_wh}",
                performed_by=payload.performed_by or "Planner"
            )

            # 2. Add to destination warehouse atomically
            tx_in, inv_dst = await InventoryEngine.process_transaction(
                session=db,
                transaction_type="TRANSFER_IN",
                sku=payload.sku,
                warehouse_id=dest_wh,
                quantity=payload.quantity,
                batch_id=payload.batch_id,
                reference_id=ref_id,
                reason=payload.reason or f"Inter-DC Transfer from {src_wh}",
                performed_by=payload.performed_by or "Planner"
            )

            # 3. Mark matching RECOMMENDED transfer as COMPLETED
            trf_match_res = await db.execute(
                select(InventoryTransfer).where(
                    and_(
                        InventoryTransfer.sku == payload.sku,
                        InventoryTransfer.source_warehouse_id == src_wh,
                        InventoryTransfer.destination_warehouse_id == dest_wh,
                        InventoryTransfer.status == "RECOMMENDED"
                    )
                )
            )
            matching_trf = trf_match_res.scalars().first()
            if matching_trf:
                matching_trf.status = "COMPLETED"
                matching_trf.dispatched_at = now_utc
                matching_trf.received_at = now_utc

            # Recalculate Risk, Alerts, Transfers & Replenishment Recommendations for network
            await RiskEngine.evaluate_inventory_risk(db, payload.sku, src_wh)
            await RiskEngine.evaluate_inventory_risk(db, payload.sku, dest_wh)
            await AlertEscalationEngine.sync_inventory_alerts(db, sku=payload.sku, warehouse_id=src_wh)
            await AlertEscalationEngine.sync_inventory_alerts(db, sku=payload.sku, warehouse_id=dest_wh)
            await NetworkBalancingEngine.identify_network_transfers(db)
            await ReplenishmentEngine.sync_recommendations(db)

            await db.commit()

            # Automatic Low-Stock Email Trigger post-commit for source warehouse
            avail_src = (inv_src.current_stock or 0) - (inv_src.reserved_stock or 0)
            reorder_src = inv_src.reorder_point or 0
            if avail_src <= reorder_src:
                trigger_async_low_stock_check(sku=payload.sku, warehouse_id=src_wh)

            # Broadcast live events
            await ws_manager.broadcast({
                "event": "TRANSFER_EXECUTED",
                "transfer_id": ref_id,
                "sku": payload.sku,
                "from": src_wh,
                "to": dest_wh,
                "quantity": payload.quantity,
                "timestamp": to_ist_iso(tx_out.timestamp)
            })
            await ws_manager.broadcast({
                "event": "INVENTORY_TRANSACTION",
                "transaction_id": tx_out.id,
                "type": "TRANSFER_OUT",
                "sku": tx_out.sku,
                "warehouse": tx_out.warehouse_id,
                "quantity": tx_out.quantity,
                "new_stock": inv_src.current_stock,
                "status": inv_src.status,
                "risk_level": inv_src.risk_level,
                "days_of_cover": inv_src.days_of_cover,
                "timestamp": to_ist_iso(tx_out.timestamp)
            })
            await ws_manager.broadcast({
                "event": "INVENTORY_TRANSACTION",
                "transaction_id": tx_in.id,
                "type": "TRANSFER_IN",
                "sku": tx_in.sku,
                "warehouse": tx_in.warehouse_id,
                "quantity": tx_in.quantity,
                "new_stock": inv_dst.current_stock,
                "status": inv_dst.status,
                "risk_level": inv_dst.risk_level,
                "days_of_cover": inv_dst.days_of_cover,
                "timestamp": to_ist_iso(tx_in.timestamp)
            })
            await ws_manager.broadcast({
                "event": "REPLENISHMENT_UPDATED",
                "timestamp": get_now_ist().isoformat()
            })

            return {
                "success": True,
                "transaction_id": tx_out.id,
                "transaction_type": "TRANSFER",
                "sku": payload.sku,
                "warehouse_id": src_wh,
                "destination_warehouse_id": dest_wh,
                "previous_stock": tx_out.previous_stock,
                "new_stock": inv_src.current_stock,
                "destination_previous_stock": tx_in.previous_stock,
                "destination_new_stock": inv_dst.current_stock,
                "current_status": inv_src.status,
                "days_of_cover": inv_src.days_of_cover,
                "message": f"Successfully transferred {payload.quantity:,} units of {payload.sku} from {src_wh} to {dest_wh}."
            }

        # Handle other standard transaction types (SALE, RECEIPT, ADJUSTMENT, CONSUMPTION)
        tx, inv = await InventoryEngine.process_transaction(
            session=db,
            transaction_type=payload.transaction_type,
            sku=payload.sku,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            batch_id=payload.batch_id,
            reference_id=payload.reference_id,
            reason=payload.reason,
            performed_by=payload.performed_by or "Planner"
        )
        
        # Recalculate Risk & Synchronize Alerts dynamically
        risk = await RiskEngine.evaluate_inventory_risk(db, payload.sku, payload.warehouse_id)
        modified_alerts = await AlertEscalationEngine.sync_inventory_alerts(db, sku=payload.sku, warehouse_id=payload.warehouse_id)
        alert_created = modified_alerts[0] if modified_alerts else None

        # Dispatch urgent notification if stockout
        if inv.status == "OUT_OF_STOCK" and alert_created and alert_created.status != "Resolved":
            await NotificationService.dispatch_notification(
                session=db,
                channel="WHATSAPP",
                recipient="+91-9876543210 (SCM On-Call)",
                alert_id=alert_created.id,
                subject=f"STOCKOUT: {payload.sku} in {payload.warehouse_id}",
                message=f"Stock for {payload.sku} at {payload.warehouse_id} has dropped to 0 units."
            )

        # Recalculate Recommendations & Network Transfers dynamically
        await NetworkBalancingEngine.identify_network_transfers(db)
        await ReplenishmentEngine.sync_recommendations(db)

        await db.commit()

        # Automatic Low-Stock Email Trigger post-commit:
        # Check if updated available stock is at or below reorder threshold
        avail_stock = (inv.current_stock or 0) - (inv.reserved_stock or 0)
        reorder_point = inv.reorder_point or 0
        tx_type = (payload.transaction_type or "").upper()
        if (avail_stock <= reorder_point) or tx_type in ["SALE", "CONSUMPTION", "TRANSFER_OUT", "TRANSFER"] or (tx_type == "ADJUSTMENT" and payload.quantity < 0):
            trigger_async_low_stock_check(sku=payload.sku, warehouse_id=payload.warehouse_id)

        # Broadcast live event via WebSocket
        event_payload = {
            "event": "INVENTORY_TRANSACTION",
            "transaction_id": tx.id,
            "type": tx.transaction_type,
            "sku": tx.sku,
            "warehouse": tx.warehouse_id,
            "quantity": tx.quantity,
            "new_stock": inv.current_stock,
            "status": inv.status,
            "risk_level": inv.risk_level,
            "days_of_cover": inv.days_of_cover,
            "alert_created": alert_created.id if alert_created else None,
            "timestamp": to_ist_iso(tx.timestamp)
        }
        await ws_manager.broadcast(event_payload)
        await ws_manager.broadcast({
            "event": "REPLENISHMENT_UPDATED",
            "timestamp": get_now_ist().isoformat()
        })

        return {
            "success": True,
            "transaction_id": tx.id,
            "transaction_type": tx.transaction_type,
            "sku": tx.sku,
            "warehouse_id": tx.warehouse_id,
            "previous_stock": tx.previous_stock,
            "new_stock": tx.new_stock,
            "current_status": inv.status,
            "days_of_cover": inv.days_of_cover,
            "alert_generated": alert_created is not None,
            "message": f"Successfully processed {tx.transaction_type} of {payload.quantity} units for {payload.sku} in {payload.warehouse_id}."
        }

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction processing error: {str(e)}")


@router.get("", response_model=List[Dict[str, Any]])
async def get_transactions(
    sku: Optional[str] = None,
    warehouse: Optional[str] = None,
    search: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = Query(10, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns transaction history from PostgreSQL supporting:
    - Default compact 10-record initial view
    - Dynamic multi-field database search (SKU, Name, Warehouse, Type, Reference, Reason, PerformedBy, ID)
    - Dynamic pagination / expansion (limit & offset)
    """
    query = (
        select(InventoryTransaction, Product)
        .join(Product, InventoryTransaction.sku == Product.sku)
        .join(Warehouse, InventoryTransaction.warehouse_id == Warehouse.id)
        .where(Product.is_active != False, Warehouse.is_active != False)
    )

    if sku:
        query = query.where(InventoryTransaction.sku == sku)
    if warehouse and warehouse != "All":
        query = query.where(InventoryTransaction.warehouse_id == warehouse)
    if transaction_type and transaction_type != "All":
        query = query.where(InventoryTransaction.transaction_type == transaction_type)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                InventoryTransaction.sku.ilike(term),
                Product.name.ilike(term),
                InventoryTransaction.warehouse_id.ilike(term),
                InventoryTransaction.transaction_type.ilike(term),
                InventoryTransaction.reference_id.ilike(term),
                InventoryTransaction.reason.ilike(term),
                InventoryTransaction.performed_by.ilike(term),
                cast(InventoryTransaction.id, String).ilike(term)
            )
        )

    query = query.order_by(InventoryTransaction.timestamp.desc()).offset(offset).limit(limit)
    res = await db.execute(query)
    records = res.all()

    return [
        {
            "id": tx.id,
            "transactionType": tx.transaction_type,
            "sku": tx.sku,
            "name": prod.name,
            "warehouse": tx.warehouse_id,
            "batchId": tx.batch_id or "-",
            "quantity": tx.quantity,
            "previousStock": tx.previous_stock,
            "newStock": tx.new_stock,
            "referenceId": tx.reference_id or "-",
            "reason": tx.reason or "-",
            "performedBy": tx.performed_by,
            "timestamp": to_ist_iso(tx.timestamp),
            "formattedTime": format_ist_datetime(tx.timestamp)
        }
        for tx, prod in records
    ]

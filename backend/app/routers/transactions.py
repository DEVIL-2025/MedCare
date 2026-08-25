from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.app.database import get_db
from backend.app.schemas.transaction import TransactionCreate, TransactionResponse
from backend.app.models.transaction import InventoryTransaction
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.risk_engine import RiskEngine
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.services.notification_service import NotificationService
from backend.app.routers.ws import ws_manager

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("", response_model=Dict[str, Any])
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes an atomic inventory transaction (SALE, CONSUMPTION, RECEIPT, ADJUSTMENT, TRANSFER).
    Triggers inventory update -> risk recalculation -> alert checks -> WebSocket broadcast.
    """
    try:
        if payload.transaction_type in ["TRANSFER_OUT", "TRANSFER"] or payload.destination_warehouse_id:
            dest_wh = (payload.destination_warehouse_id or "").strip().upper()
            src_wh = payload.warehouse_id.strip().upper()
            if not dest_wh or dest_wh == src_wh:
                raise ValueError("Destination warehouse is required and must be different from source warehouse for Inter-DC transfers.")

            ref_id = payload.reference_id or f"TRF-{payload.sku.upper()}-{src_wh}-{dest_wh}"

            # 1. Deduct from source warehouse
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

            # 2. Add to destination warehouse
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

            # Recalculate Risk & Alerts for both DCs
            await RiskEngine.evaluate_inventory_risk(db, payload.sku, src_wh)
            await RiskEngine.evaluate_inventory_risk(db, payload.sku, dest_wh)
            await AlertEscalationEngine.sync_inventory_alerts(db, sku=payload.sku, warehouse_id=src_wh)
            await AlertEscalationEngine.sync_inventory_alerts(db, sku=payload.sku, warehouse_id=dest_wh)

            await db.commit()

            # Broadcast live events
            await ws_manager.broadcast({
                "event": "TRANSFER_EXECUTED",
                "transfer_id": ref_id,
                "sku": payload.sku,
                "from": src_wh,
                "to": dest_wh,
                "quantity": payload.quantity,
                "timestamp": tx_out.timestamp.isoformat()
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
                "timestamp": tx_out.timestamp.isoformat()
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
                "timestamp": tx_in.timestamp.isoformat()
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
                "current_status": inv_src.status,
                "days_of_cover": inv_src.days_of_cover,
                "message": f"Successfully transferred {payload.quantity:,} units of {payload.sku} from {src_wh} to {dest_wh}."
            }

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

        await db.commit()

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
            "timestamp": tx.timestamp.isoformat()
        }
        await ws_manager.broadcast(event_payload)

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
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Returns recent transaction log with product names and details."""
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

    query = query.order_by(InventoryTransaction.timestamp.desc()).limit(limit)
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
            "timestamp": tx.timestamp.isoformat() if hasattr(tx.timestamp, "isoformat") else str(tx.timestamp),
            "formattedTime": tx.timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(tx.timestamp, "strftime") else str(tx.timestamp)
        }
        for tx, prod in records
    ]

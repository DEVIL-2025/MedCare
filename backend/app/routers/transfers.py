from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Dict, Any
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.routers.ws import ws_manager

router = APIRouter(prefix="/api/transfers", tags=["Transfers"])


@router.get("")
async def get_transfers(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns network-wide transfer recommendations."""
    await NetworkBalancingEngine.identify_network_transfers(db)
    await db.commit()

    active_wh_subquery = select(Warehouse.id).where(Warehouse.is_active != False)
    res = await db.execute(
        select(InventoryTransfer, Product)
        .join(Product, InventoryTransfer.sku == Product.sku)
        .where(
            Product.is_active != False,
            InventoryTransfer.source_warehouse_id.in_(active_wh_subquery),
            InventoryTransfer.destination_warehouse_id.in_(active_wh_subquery)
        )
        .order_by(InventoryTransfer.estimated_savings_inr.desc())
    )
    records = res.all()

    return [
        {
            "id": t.id,
            "sku": t.sku,
            "product_name": p.name,
            "category": p.category,
            "source_warehouse": t.source_warehouse_id,
            "destination_warehouse": t.destination_warehouse_id,
            "batch_id": t.batch_id,
            "quantity": t.quantity,
            "available_at_source": t.available_at_source,
            "lead_time_days": t.transfer_lead_time_days,
            "estimated_savings_inr": t.estimated_savings_inr,
            "reason": t.reason,
            "status": t.status,
            "dispatched_at": t.dispatched_at.isoformat() if t.dispatched_at else None,
            "received_at": t.received_at.isoformat() if t.received_at else None,
        }
        for t, p in records
    ]


@router.post("/{id}/execute")
async def execute_transfer(id: str, db: AsyncSession = Depends(get_db)):
    """
    Executes inter-DC transfer:
    1. Deducts quantity from source warehouse (TRANSFER_OUT)
    2. Adds quantity as inbound / stock to destination warehouse (TRANSFER_IN)
    3. Updates transfer status to COMPLETED
    4. Recalculates transfers, replenishment recommendations, and alerts
    5. Broadcasts WebSocket event
    """
    res = await db.execute(select(InventoryTransfer).where(InventoryTransfer.id == id))
    trf = res.scalars().first()
    if not trf:
        raise HTTPException(status_code=404, detail="Transfer not found")

    try:
        # Deduct from Source
        tx_out, inv_src = await InventoryEngine.process_transaction(
            session=db,
            transaction_type="TRANSFER_OUT",
            sku=trf.sku,
            warehouse_id=trf.source_warehouse_id,
            quantity=trf.quantity,
            batch_id=trf.batch_id,
            reference_id=trf.id,
            reason=f"Inter-DC Transfer to {trf.destination_warehouse_id}",
            performed_by="Control Tower Engine"
        )

        # Add to Destination
        tx_in, inv_dst = await InventoryEngine.process_transaction(
            session=db,
            transaction_type="TRANSFER_IN",
            sku=trf.sku,
            warehouse_id=trf.destination_warehouse_id,
            quantity=trf.quantity,
            batch_id=trf.batch_id,
            reference_id=trf.id,
            reason=f"Inter-DC Transfer from {trf.source_warehouse_id}",
            performed_by="Control Tower Engine"
        )

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        trf.status = "COMPLETED"
        trf.dispatched_at = now_utc
        trf.received_at = now_utc

        # Recalculate risk & sync alerts on both distribution centers
        await AlertEscalationEngine.sync_inventory_alerts(db, sku=trf.sku, warehouse_id=trf.source_warehouse_id)
        await AlertEscalationEngine.sync_inventory_alerts(db, sku=trf.sku, warehouse_id=trf.destination_warehouse_id)
        await NetworkBalancingEngine.identify_network_transfers(db)
        await ReplenishmentEngine.sync_recommendations(db)

        await db.commit()

        # Broadcast live event
        await ws_manager.broadcast({
            "event": "TRANSFER_EXECUTED",
            "transfer_id": trf.id,
            "sku": trf.sku,
            "from": trf.source_warehouse_id,
            "to": trf.destination_warehouse_id,
            "quantity": trf.quantity,
            "savings": trf.estimated_savings_inr,
            "timestamp": now_utc.isoformat()
        })
        await ws_manager.broadcast({
            "event": "REPLENISHMENT_UPDATED",
            "timestamp": now_utc.isoformat()
        })

        return {
            "success": True,
            "transfer_id": trf.id,
            "message": f"Successfully transferred {trf.quantity:,} units of {trf.sku} from {trf.source_warehouse_id} to {trf.destination_warehouse_id}."
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Transfer execution failed: {str(e)}")


@router.post("/{id}/approve")
async def approve_transfer(id: str, db: AsyncSession = Depends(get_db)):
    """Alias for transfer execution / approval."""
    return await execute_transfer(id, db)

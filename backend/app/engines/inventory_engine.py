import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.app.models.inventory import Inventory
from backend.app.models.batch import Batch
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.transaction import InventoryTransaction
from backend.app.engines.expiry_fefo_engine import ExpiryFEFOEngine
from backend.app.utils.timezone import get_today_ist


class InventoryEngine:
    """Core inventory engine managing stock balances, thresholds, and transaction validation."""

    @staticmethod
    def evaluate_inventory_status(
        current_stock: int,
        reorder_point: int,
        safety_stock: int
    ) -> Tuple[str, str]:
        """
        Determines the inventory status and risk level based on configured thresholds.
        Status: OUT_OF_STOCK, CRITICAL, LOW_STOCK, OVERSTOCK, HEALTHY
        Risk: critical, high, medium, low
        """
        if current_stock <= 0:
            return "OUT_OF_STOCK", "critical"
        elif current_stock < safety_stock:
            return "CRITICAL", "critical"
        elif current_stock < reorder_point:
            return "LOW_STOCK", "high"
        elif current_stock > reorder_point * 2.2:
            return "OVERSTOCK", "low"
        elif current_stock < reorder_point * 1.3:
            return "HEALTHY", "medium"
        else:
            return "HEALTHY", "low"

    @staticmethod
    async def process_transaction(
        session: AsyncSession,
        transaction_type: str,
        sku: str,
        warehouse_id: str,
        quantity: int,
        batch_id: Optional[str] = None,
        expiry_date: Optional[Any] = None,
        reference_id: Optional[str] = None,
        reason: Optional[str] = None,
        performed_by: str = "Planner"
    ) -> Tuple[InventoryTransaction, Inventory]:
        """
        Validates and applies atomic inventory transactions:
        - SALE / CONSUMPTION: Deducts stock (FEFO if batch_id not specified)
        - RECEIPT: Adds stock and registers/updates batch
        - ADJUSTMENT: Directly sets/adjusts variance
        - TRANSFER_OUT / TRANSFER_IN: Cross-warehouse stock movement
        """
        # 1. Validate quantity
        if quantity <= 0 and transaction_type.upper() != "ADJUSTMENT":
            raise ValueError(f"Transaction quantity must be positive. Received: {quantity}")

        # 2. Validate warehouse_id
        if not warehouse_id or str(warehouse_id).strip().lower() in [
            "all", "all warehouses", "all_warehouses", "network", "network rollup", "all_dcs", "null", "undefined"
        ]:
            raise ValueError(
                f"Invalid warehouse identifier '{warehouse_id}'. A specific, physical warehouse (e.g. MUM-01, DEL-02, PAT-01) must be selected."
            )

        clean_wh_id = warehouse_id.strip().upper()
        wh_res = await session.execute(select(Warehouse).where(Warehouse.id == clean_wh_id))
        warehouse = wh_res.scalars().first()
        if not warehouse:
            raise ValueError(
                f"Warehouse '{warehouse_id}' does not exist in the database. Please select a registered distribution center."
            )
        if not warehouse.is_active:
            raise ValueError(
                f"Warehouse '{warehouse.name}' ({clean_wh_id}) is decommissioned / inactive."
            )

        # 3. Validate Product SKU
        clean_sku = sku.strip().upper() if sku else ""
        prod_res = await session.execute(select(Product).where(Product.sku == clean_sku))
        product = prod_res.scalars().first()
        if not product:
            raise ValueError(f"Invalid SKU: '{sku}' does not exist in master catalog.")
        if not product.is_active:
            raise ValueError(f"Product '{product.name}' ({clean_sku}) is archived / inactive.")

        # 4. Fetch or create Inventory record
        inv_res = await session.execute(
            select(Inventory).where(and_(Inventory.sku == clean_sku, Inventory.warehouse_id == clean_wh_id))
        )
        inv = inv_res.scalars().first()
        if not inv:
            inv = Inventory(
                sku=clean_sku,
                warehouse_id=clean_wh_id,
                current_stock=0,
                reserved_stock=0,
                inbound_stock=0,
                reorder_point=product.default_reorder_point,
                safety_stock=product.default_safety_stock,
                status="OUT_OF_STOCK",
                risk_level="critical",
                days_of_cover=0.0
            )
            session.add(inv)
            await session.flush()

        prev_stock = inv.current_stock
        tx_type = transaction_type.upper()
        today = get_today_ist()
        allocated_batch_id = batch_id

        if tx_type in ["SALE", "CONSUMPTION", "TRANSFER_OUT"]:
            if inv.available_stock < quantity:
                raise ValueError(
                    f"Insufficient stock for {clean_sku} in {clean_wh_id}. Available: {inv.available_stock}, Requested: {quantity}"
                )
            new_stock = prev_stock - quantity
            inv.current_stock = new_stock

            if batch_id:
                # Deduct from specific requested batch, or fall back to multi-batch FEFO if quantity exceeds single batch
                b_res = await session.execute(
                    select(Batch).where(and_(Batch.id == batch_id, Batch.warehouse_id == clean_wh_id, Batch.sku == clean_sku))
                )
                b = b_res.scalars().first()
                if b and not b.is_quarantined and b.status not in ["EXPIRED", "QUARANTINED", "DEPLETED"] and b.expiry_date > today and b.available_quantity >= quantity:
                    b.quantity -= quantity
                    if b.quantity == 0:
                        b.status = "DEPLETED"
                else:
                    # Multi-batch FEFO allocation across warehouse batches
                    allocations = await ExpiryFEFOEngine.allocate_fefo_batches(
                        session=session,
                        sku=clean_sku,
                        warehouse_id=clean_wh_id,
                        required_quantity=quantity
                    )
                    if not allocations:
                        raise ValueError(f"No valid non-expired batches available to allocate for {clean_sku} in {clean_wh_id}.")
                    for alloc in allocations:
                        ab = alloc["batch"]
                        deduct = alloc["allocated_quantity"]
                        ab.quantity -= deduct
                        if ab.quantity == 0:
                            ab.status = "DEPLETED"
                    allocated_batch_id = allocations[0]["batch_id"] if allocations else batch_id
            else:
                # Centralized FEFO allocation
                allocations = await ExpiryFEFOEngine.allocate_fefo_batches(
                    session=session,
                    sku=clean_sku,
                    warehouse_id=clean_wh_id,
                    required_quantity=quantity
                )
                if not allocations:
                    raise ValueError(f"No valid non-expired batches available to allocate for {clean_sku} in {clean_wh_id}.")
                
                for alloc in allocations:
                    b = alloc["batch"]
                    deduct = alloc["allocated_quantity"]
                    b.quantity -= deduct
                    if b.quantity == 0:
                        b.status = "DEPLETED"

                if len(allocations) == 1:
                    allocated_batch_id = allocations[0]["batch_id"]

        elif tx_type in ["RECEIPT", "TRANSFER_IN"]:
            new_stock = prev_stock + quantity
            inv.current_stock = new_stock

            # Parse user-specified expiry date if provided
            parsed_exp_date = None
            if expiry_date:
                if isinstance(expiry_date, datetime):
                    parsed_exp_date = expiry_date.date()
                elif hasattr(expiry_date, "year") and hasattr(expiry_date, "month") and hasattr(expiry_date, "day"):
                    parsed_exp_date = expiry_date
                elif isinstance(expiry_date, str) and expiry_date.strip():
                    try:
                        parsed_exp_date = datetime.strptime(expiry_date.strip()[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass

            # Add to or create batch
            default_shelf_life = product.shelf_life_days if (product and product.shelf_life_days) else 730
            final_exp_date = parsed_exp_date or (today + timedelta(days=default_shelf_life))
            d_to_exp = (final_exp_date - today).days
            initial_status = "EXPIRED" if d_to_exp <= 0 else ("CRITICAL" if d_to_exp <= 30 else ("NEAR_EXPIRY" if d_to_exp <= 90 else "ACTIVE"))

            if batch_id:
                dest_batch_id = f"{batch_id}-{clean_wh_id}"
                b_res = await session.execute(
                    select(Batch).where(
                        and_(
                            Batch.warehouse_id == clean_wh_id,
                            or_(Batch.id == batch_id, Batch.id == dest_batch_id)
                        )
                    )
                )
                existing_b = b_res.scalars().first()
                if existing_b:
                    existing_b.quantity += quantity
                    if parsed_exp_date:
                        existing_b.expiry_date = parsed_exp_date
                        existing_d_exp = (existing_b.expiry_date - today).days
                        existing_b.status = "EXPIRED" if existing_d_exp <= 0 else ("CRITICAL" if existing_d_exp <= 30 else ("NEAR_EXPIRY" if existing_d_exp <= 90 else "ACTIVE"))
                    elif existing_b.status in ["DEPLETED", "EXPIRED"]:
                        existing_b.status = "ACTIVE"
                    allocated_batch_id = existing_b.id
                else:
                    # Check if source batch exists to copy expiry_date / mfg_date
                    src_b_res = await session.execute(select(Batch).where(Batch.id == batch_id))
                    src_b = src_b_res.scalars().first()
                    exp_date = parsed_exp_date or (src_b.expiry_date if src_b else final_exp_date)
                    mfg_date = src_b.mfg_date if src_b else today

                    target_batch_id = dest_batch_id if (src_b and src_b.warehouse_id != clean_wh_id) else batch_id
                    new_b = Batch(
                        id=target_batch_id,
                        sku=clean_sku,
                        warehouse_id=clean_wh_id,
                        quantity=quantity,
                        reserved_quantity=0,
                        mfg_date=mfg_date,
                        expiry_date=exp_date,
                        status=initial_status
                    )
                    session.add(new_b)
                    allocated_batch_id = target_batch_id
            else:
                uid_suffix = uuid.uuid4().hex[:6].upper()
                now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
                new_batch_id = f"BAT-{clean_sku}-{clean_wh_id}-{now_ts}-{uid_suffix}"
                allocated_batch_id = new_batch_id
                new_b = Batch(
                    id=new_batch_id,
                    sku=clean_sku,
                    warehouse_id=clean_wh_id,
                    quantity=quantity,
                    reserved_quantity=0,
                    mfg_date=today,
                    expiry_date=final_exp_date,
                    status=initial_status
                )
                session.add(new_b)

        elif tx_type == "ADJUSTMENT":
            # Direct count adjustment: quantity is the difference (can be negative/positive handled via delta)
            new_stock = max(0, prev_stock + quantity)
            inv.current_stock = new_stock
        else:
            raise ValueError(f"Unsupported transaction type: {transaction_type}")

        # Recalculate status, risk, and days of cover
        status, risk = InventoryEngine.evaluate_inventory_status(
            inv.current_stock, inv.reorder_point, inv.safety_stock
        )
        inv.status = status
        inv.risk_level = risk
        
        # Estimate updated days of cover based on safety stock / reorder reference
        daily_ref = max(1.0, float(inv.reorder_point or 500) / 30.0)
        inv.days_of_cover = round(float(inv.current_stock) / daily_ref, 1)

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        inv.last_recalculated_at = now_utc

        # Log transaction with collision-free reference ID
        now_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        uid_ref = uuid.uuid4().hex[:6].upper()
        tx = InventoryTransaction(
            transaction_type=tx_type,
            sku=clean_sku,
            warehouse_id=clean_wh_id,
            batch_id=allocated_batch_id,
            quantity=quantity if tx_type in ["RECEIPT", "TRANSFER_IN", "ADJUSTMENT"] else -quantity,
            previous_stock=prev_stock,
            new_stock=new_stock,
            reference_id=reference_id or f"TX-{now_utc_ms}-{uid_ref}",
            reason=reason or f"Standard {tx_type} operation",
            performed_by=performed_by,
            timestamp=now_utc
        )
        session.add(tx)
        await session.flush()

        return tx, inv

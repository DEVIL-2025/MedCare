from datetime import date, timedelta
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.models.inventory import Inventory
from backend.app.models.warehouse import Warehouse
from backend.app.models.product import Product
from backend.app.models.batch import Batch
from backend.app.models.transfer import InventoryTransfer
from backend.app.ml.predict import PredictionService
from backend.app.config import settings


class NetworkBalancingEngine:
    """
    P1 Multi-DC Network Stock Balancing & Expiry-Aware Transfer Engine.
    Matches shortage warehouses with surplus/near-expiry stock in excess warehouses.
    Optimized with bulk pre-fetching and in-memory matching.
    """

    @staticmethod
    async def identify_network_transfers(session: AsyncSession) -> List[InventoryTransfer]:
        """
        Scans all SKUs across the DC network to discover and record optimal FEFO transfer candidates.
        Bulk pre-fetches all inventories, batches, and ML forecasts to eliminate N+1 queries.
        """
        today = date(2026, 8, 24)

        # 1. Bulk pre-fetch all records
        prods_res = await session.execute(select(Product).where(Product.is_active != False))
        products = prods_res.scalars().all()

        inv_res = await session.execute(
            select(Inventory).join(Warehouse, Inventory.warehouse_id == Warehouse.id).where(Warehouse.is_active != False)
        )
        all_inventories = inv_res.scalars().all()
        inventories_by_sku: Dict[str, List[Inventory]] = {}
        for inv in all_inventories:
            inventories_by_sku.setdefault(inv.sku, []).append(inv)

        batches_res = await session.execute(
            select(Batch).where(
                and_(
                    Batch.quantity > 0,
                    Batch.expiry_date > today
                )
            ).order_by(Batch.expiry_date.asc())
        )
        all_batches = batches_res.scalars().all()
        batches_by_sku_wh: Dict[str, List[Batch]] = {}
        for b in all_batches:
            k = f"{b.sku}_{b.warehouse_id}"
            batches_by_sku_wh.setdefault(k, []).append(b)

        trfs_res = await session.execute(select(InventoryTransfer))
        existing_trfs_map = {t.id: t for t in trfs_res.scalars().all()}

        all_forecasts = await PredictionService.predict_all_demands(session, 30)

        transfers = []

        for prod in products:
            sku = prod.sku
            inventories = inventories_by_sku.get(sku, [])

            shortage_nodes = []
            excess_nodes = []

            for inv in inventories:
                f_data = all_forecasts.get(f"{sku}_{inv.warehouse_id}", {
                    "sensed_daily": 50.0,
                    "forecast_demand_next_30d": 1500
                })
                daily_rate = max(1.0, float(f_data.get("sensed_daily", 50.0)))
                doc = inv.available_stock / daily_rate

                if doc <= 14.0 or inv.current_stock < inv.reorder_point or inv.status in ["CRITICAL", "LOW_STOCK", "OUT_OF_STOCK"]:
                    shortage_nodes.append({
                        "warehouse_id": inv.warehouse_id,
                        "current_stock": inv.current_stock,
                        "available_stock": inv.available_stock,
                        "daily_rate": daily_rate,
                        "doc": doc,
                        "deficit": max(prod.moq, int(inv.reorder_point - inv.current_stock))
                    })
                elif doc >= 20.0 or inv.current_stock >= inv.reorder_point * 1.2:
                    batches = batches_by_sku_wh.get(f"{sku}_{inv.warehouse_id}", [])
                    near_expiry_qty = sum(
                        b.quantity for b in batches if (b.expiry_date - today).days <= settings.EXPIRY_AT_RISK_DAYS
                    )

                    excess_nodes.append({
                        "warehouse_id": inv.warehouse_id,
                        "current_stock": inv.current_stock,
                        "available_stock": inv.available_stock,
                        "surplus": max(0, int(inv.available_stock - inv.safety_stock)),
                        "near_expiry_qty": near_expiry_qty,
                        "batches": batches
                    })

            # Prioritize most urgent shortage (lowest DOC) and highest near-expiry surplus source
            shortage_nodes.sort(key=lambda x: x["doc"])
            excess_nodes.sort(key=lambda x: (x["near_expiry_qty"], x["surplus"]), reverse=True)

            # Match Shortage with Excess
            for s_node in shortage_nodes:
                for e_node in excess_nodes:
                    if s_node["warehouse_id"] == e_node["warehouse_id"]:
                        continue

                    available_transfer = min(e_node["surplus"], s_node["deficit"])
                    if available_transfer >= 200:
                        # Find best batch from source (FEFO: earliest valid expiry)
                        chosen_batch = e_node["batches"][0] if e_node["batches"] else None
                        batch_id = chosen_batch.id if chosen_batch else None
                        
                        transfer_qty = min(available_transfer, 5000)
                        # Round to nearest 100
                        transfer_qty = max(100, int((transfer_qty + 99) // 100 * 100))
                        savings = round(transfer_qty * prod.unit_cost * 0.85, 2)  # Avoided procurement + writeoff

                        days_to_exp = (chosen_batch.expiry_date - today).days if chosen_batch else 60
                        reason = (
                            f"FEFO Transfer: {transfer_qty:,} units from {e_node['warehouse_id']} "
                            f"(batch expiring in {days_to_exp}d) to {s_node['warehouse_id']} "
                            f"(stockout risk in {round(s_node['doc'], 1)}d)."
                        )

                        trf_id = f"TRF-{sku}-{e_node['warehouse_id']}-{s_node['warehouse_id']}"
                        existing_trf = existing_trfs_map.get(trf_id)

                        if existing_trf:
                            if existing_trf.status == "RECOMMENDED":
                                existing_trf.quantity = transfer_qty
                                existing_trf.batch_id = batch_id
                                existing_trf.available_at_source = e_node["available_stock"]
                                existing_trf.estimated_savings_inr = savings
                                existing_trf.reason = reason
                                transfers.append(existing_trf)
                        else:
                            trf = InventoryTransfer(
                                id=trf_id,
                                sku=sku,
                                source_warehouse_id=e_node["warehouse_id"],
                                destination_warehouse_id=s_node["warehouse_id"],
                                batch_id=batch_id,
                                quantity=transfer_qty,
                                available_at_source=e_node["available_stock"],
                                transfer_lead_time_days=3,
                                estimated_savings_inr=savings,
                                reason=reason,
                                status="RECOMMENDED"
                            )
                            transfers.append(trf)
                            session.add(trf)

                        # Deduct from excess node surplus so it's not double counted
                        e_node["surplus"] -= transfer_qty

        await session.flush()
        return transfers

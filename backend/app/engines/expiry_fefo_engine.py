from datetime import date
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.models.batch import Batch
from backend.app.models.product import Product
from backend.app.config import settings
from backend.app.utils.timezone import get_today_ist


class ExpiryFEFOEngine:
    """
    P1 Expiry Tracking and FEFO (First Expiry, First Out) Engine.
    """

    @staticmethod
    def categorize_batch_expiry(
        expiry_date: date, today: Optional[date] = None
    ) -> Tuple[str, int]:
        """Categorizes batch into Expiry Risk Buckets: CRITICAL, AT_RISK, WATCH, NORMAL, EXPIRED."""
        today = today or get_today_ist()
        days_to_expiry = (expiry_date - today).days

        if days_to_expiry <= 0:
            return "EXPIRED", days_to_expiry
        elif days_to_expiry <= settings.EXPIRY_CRITICAL_DAYS:
            return "CRITICAL", days_to_expiry
        elif days_to_expiry <= settings.EXPIRY_AT_RISK_DAYS:
            return "AT_RISK", days_to_expiry
        elif days_to_expiry <= settings.EXPIRY_WATCH_DAYS:
            return "WATCH", days_to_expiry
        else:
            return "NORMAL", days_to_expiry

    @staticmethod
    async def allocate_fefo_batches(
        session: AsyncSession,
        sku: str,
        warehouse_id: str,
        required_quantity: int
    ) -> List[Dict[str, Any]]:
        """
        Selects batches in strict FEFO order, skipping expired or quarantined batches.
        """
        clean_sku = sku.strip().upper() if sku else ""
        clean_wh_id = warehouse_id.strip() if warehouse_id else ""
        today = get_today_ist()

        batches_res = await session.execute(
            select(Batch).where(
                and_(
                    Batch.sku == clean_sku,
                    Batch.warehouse_id == clean_wh_id,
                    Batch.expiry_date > today,
                    Batch.is_quarantined == False,
                    Batch.status.notin_(["EXPIRED", "QUARANTINED", "DEPLETED"]),
                    Batch.quantity > 0
                )
            ).order_by(Batch.expiry_date.asc())
        )
        available_batches = batches_res.scalars().all()
        
        allocations = []
        remaining = required_quantity

        for b in available_batches:
            if remaining <= 0:
                break
            usable = b.available_quantity
            if usable <= 0:
                continue
            allocated = min(usable, remaining)
            allocations.append({
                "batch_id": b.id,
                "expiry_date": b.expiry_date.isoformat(),
                "allocated_quantity": allocated,
                "days_to_expiry": (b.expiry_date - today).days,
                "batch": b
            })
            remaining -= allocated

        return allocations

    @staticmethod
    async def calculate_aging_and_expiry_summary(session: AsyncSession) -> Dict[str, Any]:
        """
        Calculates network-wide inventory aging buckets and total financial value at risk.
        Distinguishes inventory age (today - mfg_date) from remaining shelf life (expiry_date - today).
        """
        today = get_today_ist()
        batches_res = await session.execute(
            select(Batch, Product).join(Product, Batch.sku == Product.sku).where(
                and_(
                    Batch.quantity > 0,
                    Batch.is_quarantined == False
                )
            )
        )
        records = batches_res.all()

        buckets = {
            "0-30": {"units": 0, "value": 0.0, "label": "0 - 30 (New)", "tone": "good"},
            "31-60": {"units": 0, "value": 0.0, "label": "31 - 60", "tone": "warning"},
            "61-90": {"units": 0, "value": 0.0, "label": "61 - 90", "tone": "warning"},
            "91-180": {"units": 0, "value": 0.0, "label": "91 - 180", "tone": "critical"},
            "180+": {"units": 0, "value": 0.0, "label": "180+ (At Risk)", "tone": "critical"},
        }
        total_val = 0.0
        at_risk_val = 0.0
        expired_val = 0.0
        expiry_risk_units = 0

        for batch, prod in records:
            mfg_date = batch.mfg_date or batch.expiry_date or today
            age_days = max(0, (today - mfg_date).days)
            unit_cost = float(getattr(prod, "unit_cost", 0.0) or 0.0)
            batch_qty = int(batch.quantity or 0)
            batch_val = batch_qty * unit_cost
            total_val += batch_val

            days_to_exp = (batch.expiry_date - today).days if batch.expiry_date else 999
            if days_to_exp <= 0:
                expired_val += batch_val
            elif days_to_exp <= settings.EXPIRY_AT_RISK_DAYS:
                at_risk_val += batch_val
                expiry_risk_units += batch_qty

            if age_days <= 30:
                buckets["0-30"]["units"] += batch_qty
                buckets["0-30"]["value"] += batch_val
            elif age_days <= 60:
                buckets["31-60"]["units"] += batch_qty
                buckets["31-60"]["value"] += batch_val
            elif age_days <= 90:
                buckets["61-90"]["units"] += batch_qty
                buckets["61-90"]["value"] += batch_val
            elif age_days <= 180:
                buckets["91-180"]["units"] += batch_qty
                buckets["91-180"]["value"] += batch_val
            else:
                buckets["180+"]["units"] += batch_qty
                buckets["180+"]["value"] += batch_val

        summary_list = []
        for k, b in buckets.items():
            pct = round((b["value"] / max(1.0, total_val)) * 100.0, 1)
            val_cr = round(b["value"] / 10000000.0, 2)
            summary_list.append({
                "bucket": b["label"],
                "value": f"₹{val_cr} Cr",
                "pct": f"{pct}%",
                "tone": b["tone"]
            })

        return {
            "total_inventory_value_cr": round(total_val / 10000000.0, 2),
            "at_risk_value_cr": round(at_risk_val / 10000000.0, 2),
            "expired_value_cr": round(expired_val / 10000000.0, 2),
            "usable_value_cr": round(max(0.0, total_val - at_risk_val - expired_val) / 10000000.0, 2),
            "expiry_risk_units": expiry_risk_units,
            "aging_summary": summary_list
        }

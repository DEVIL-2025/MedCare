from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List

from backend.app.database import get_db
from backend.app.models.settings import SystemSetting
from backend.app.models.transaction import InventoryTransaction
from backend.app.schemas.settings import SettingsUpdateRequest

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
async def get_system_settings(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Returns dynamic system parameters, stakeholder users, and live transaction audit trail."""
    res = await db.execute(select(SystemSetting))
    settings_items = res.scalars().all()

    settings_dict = {s.key: s.value for s in settings_items}

    users = [
        {"name": "Dr. Aditi Rao", "email": "aditi.rao@medcarepharma.com", "role": "Lead SCM Demand Planner", "status": "Active"},
        {"name": "Rohan Mehta", "email": "rohan.mehta@medcarepharma.com", "role": "Regional SCM Manager", "status": "Active"},
        {"name": "Sara Iyer", "email": "sara.iyer@medcarepharma.com", "role": "Procurement Lead", "status": "Active"},
        {"name": "Vikram Nair", "email": "vikram.nair@medcarepharma.com", "role": "VP Global Supply Chain", "status": "Active"},
    ]

    tx_res = await db.execute(select(InventoryTransaction).order_by(InventoryTransaction.timestamp.desc()).limit(8))
    tx_logs = tx_res.scalars().all()

    audit_logs = [
        {
            "action": f"{tx.transaction_type.replace('_', ' ').title()}: {tx.quantity:,} units of {tx.sku} @ {tx.warehouse_id}",
            "user": "SCM Operator",
            "time": tx.timestamp.strftime("%d %b %Y, %I:%M %p")
        }
        for tx in tx_logs
    ]
    if not audit_logs:
        audit_logs = [
            {"action": "Initial Safety Stock Parameters calibrated", "user": "System", "time": "24 Aug 2026, 09:00 AM"}
        ]

    return {
        "parameters": settings_dict,
        "users": users,
        "audit_logs": audit_logs
    }


@router.put("")
async def update_system_settings(
    payload: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Dynamically updates system parameters and immediately takes effect in backend engines."""

    for key, value in payload.settings.items():
        res = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = res.scalars().first()

        if setting:
            setattr(setting, "value", str(value))
        else:
            new_s = SystemSetting(
                key=key,
                category="Custom",
                value=str(value)
            )
            db.add(new_s)

    await db.commit()

    return {
        "success": True,
        "message": "System settings updated successfully."
    }

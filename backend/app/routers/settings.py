from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Dict, Any, List

from backend.app.database import get_db
from backend.app.models.settings import SystemSetting
from backend.app.models.transaction import InventoryTransaction
from backend.app.models.auth import User, AuditLog
from backend.app.schemas.settings import SettingsUpdateRequest
from backend.app.dependencies.auth import require_permission, get_optional_user

from backend.app.utils.timezone import format_ist_datetime, to_ist_iso

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
async def get_system_settings(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Returns dynamic system parameters, stakeholder users, and live transaction/system audit trail from PostgreSQL."""
    res = await db.execute(select(SystemSetting))
    settings_items = res.scalars().all()

    settings_dict = {s.key: s.value for s in settings_items}

    # Query real users from database
    user_res = await db.execute(select(User).order_by(User.created_at.asc()))
    db_users = user_res.scalars().all()

    users = [
        {
            "name": u.full_name,
            "email": u.email,
            "role": u.role.name if u.role else u.role_id,
            "status": "Active" if u.is_active else "Inactive"
        }
        for u in db_users
    ] if db_users else []

    # Query latest audit logs from PostgreSQL
    audit_res = await db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(10))
    db_audits = audit_res.scalars().all()

    if db_audits:
        audit_logs = [
            {
                "action": f"{a.action}: {a.new_value or a.module}",
                "user": a.user_id,
                "time": format_ist_datetime(a.created_at, "%d %b %Y, %I:%M:%S %p IST") if a.created_at else "Recent",
                "iso": to_ist_iso(a.created_at)
            }
            for a in db_audits
        ]
    else:
        tx_res = await db.execute(select(InventoryTransaction).order_by(InventoryTransaction.timestamp.desc()).limit(8))
        tx_logs = tx_res.scalars().all()
        audit_logs = [
            {
                "action": f"{tx.transaction_type.replace('_', ' ').title()}: {tx.quantity:,} units of {tx.sku} @ {tx.warehouse_id}",
                "user": "SCM Operator",
                "time": format_ist_datetime(tx.timestamp, "%d %b %Y, %I:%M:%S %p IST") if tx.timestamp else "Recent",
                "iso": to_ist_iso(tx.timestamp)
            }
            for tx in tx_logs
        ]

    return {
        "parameters": settings_dict,
        "users": users,
        "audit_logs": audit_logs
    }


@router.put("")
async def update_system_settings(
    payload: SettingsUpdateRequest,
    current_user: User = Depends(require_permission("system.configuration")),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Dynamically updates system parameters and immediately takes effect in backend engines (Admin Only)."""

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

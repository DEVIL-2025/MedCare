from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional

from backend.app.database import get_db
from backend.app.models.notification import NotificationLog
from backend.app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


from backend.app.utils.timezone import format_ist_datetime, to_ist_iso

@router.get("")
async def get_notification_logs(
    channel: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns multi-channel notification dispatch logs."""
    query = select(NotificationLog)
    if channel and channel != "All":
        query = query.where(NotificationLog.channel == channel.upper())

    query = query.order_by(NotificationLog.timestamp.desc()).limit(limit)
    res = await db.execute(query)
    logs = res.scalars().all()

    return [
        {
            "id": log.id,
            "alertId": log.alert_id or "—",
            "channel": log.channel,
            "recipient": log.recipient,
            "subject": log.subject or "Alert Notification",
            "messageBody": log.message_body,
            "status": log.status,
            "timestamp": format_ist_datetime(log.timestamp, "%d %b %Y, %I:%M:%S %p IST") if log.timestamp else "—",
            "iso": to_ist_iso(log.timestamp)
        }
        for log in logs
    ]


@router.post("/send")
async def send_test_notification(
    channel: str,
    recipient: str,
    subject: str,
    message: str,
    alert_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Dispatches a simulated notification and records it in the log."""
    try:
        log = await NotificationService.dispatch_notification(
            session=db,
            channel=channel,
            recipient=recipient,
            alert_id=alert_id,
            subject=subject,
            message=message
        )
        await db.commit()
        return {"success": True, "notification_id": log.id, "status": log.status}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/low-stock-check")
@router.get("/low-stock-check")
async def run_low_stock_email_check(
    sku: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    force_ignore_cooldown: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Scans PostgreSQL for items below reorder threshold and dispatches low-stock email alerts.
    Supports 24-hour deduplication and can be called by cron jobs or automated schedulers.
    """
    from backend.app.services.email_alert_service import EmailAlertService
    try:
        dispatched = await EmailAlertService.check_and_dispatch_low_stock_email_alerts(
            session=db,
            target_sku=sku,
            target_warehouse_id=warehouse_id,
            force_ignore_cooldown=force_ignore_cooldown
        )
        return {
            "success": True,
            "dispatched_count": len(dispatched),
            "alerts": dispatched,
            "message": f"Processed low-stock email check. {len(dispatched)} alerts dispatched."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed executing low-stock check: {str(e)}")


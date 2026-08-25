from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from backend.app.database import get_db
from backend.app.models.alert import Alert
from backend.app.models.warehouse import Warehouse
from backend.app.models.escalation import AlertEscalation
from backend.app.models.transaction import InventoryTransaction
from backend.app.schemas.alert import AlertActionRequest
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.routers.ws import ws_manager
from backend.app.utils.timezone import get_now_ist, get_today_ist, format_ist_datetime, format_ist_date

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("")
async def get_alerts_overview(
    category: Optional[str] = "All Alerts",
    search: Optional[str] = "",
    warehouse: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns dynamically computed alerts list, severity summary counts,
    root-cause alert type distributions, and recent audit activity from the database.
    """
    # 1. Dynamically synchronize alerts with live inventory status
    await AlertEscalationEngine.sync_inventory_alerts(db, warehouse_id=warehouse)
    await db.commit()

    # 2. Query synchronized alerts from PostgreSQL (Active warehouses only)
    query = (
        select(Alert)
        .join(Warehouse, Alert.warehouse_id == Warehouse.id)
        .where(Warehouse.is_active != False)
    )
    if warehouse and warehouse != "All":
        query = query.where(Alert.warehouse_id == warehouse)
    
    query = query.order_by(Alert.created_at.desc())
    res = await db.execute(query)
    all_alerts = res.scalars().all()

    # Dynamic Severity Counts
    counts = {
        "critical": len([a for a in all_alerts if a.severity == "critical" and a.status != "Resolved"]),
        "warning": len([a for a in all_alerts if a.severity == "warning" and a.status != "Resolved"]),
        "medium": len([a for a in all_alerts if a.severity == "medium" and a.status != "Resolved"]),
        "info": len([a for a in all_alerts if a.severity == "info" and a.status != "Resolved"]),
        "good": len([a for a in all_alerts if a.status == "Resolved"]),
        "total": len([a for a in all_alerts if a.status != "Resolved"])
    }

    # Filter by category/tab
    tab_map = {
        "All Alerts": None,
        "Critical": "critical",
        "Warning": "warning",
        "Medium": "medium",
        "Resolved": "good"
    }
    wanted = tab_map.get(category or "All Alerts")
    search_lower = search.lower().strip() if search else ""

    filtered_alerts = []
    for a in all_alerts:
        if wanted is None:
            # Main "All Alerts" tab: Exclude Resolved alerts
            if a.status == "Resolved":
                continue
        elif wanted == "good":
            # "Resolved" tab: Include ONLY Resolved alerts
            if a.status != "Resolved":
                continue
        else:
            # Severity tabs (Critical, Warning, Medium): Exclude Resolved alerts and match severity
            if a.severity != wanted or a.status == "Resolved":
                continue

        if search_lower:
            match_p = search_lower in (a.product_name or "").lower()
            match_s = search_lower in (a.sku or "").lower()
            match_t = search_lower in (a.alert_type or "").lower()
            if not (match_p or match_s or match_t):
                continue

        filtered_alerts.append({
            "id": a.id,
            "type": a.alert_type.replace("_", " ").title(),
            "category": a.severity,
            "sku": a.sku or "—",
            "product": a.product_name or "Multiple SKUs",
            "warehouse": a.warehouse_id or "Network",
            "detail": a.detail,
            "cause": a.cause,
            "recommendedAction": a.recommended_action,
            "status": a.status,
            "owner": a.owner,
            "escalationLevel": a.escalation_level,
            "isEscalated": a.is_escalated,
            "createdAt": format_ist_datetime(a.created_at),
            "createdAtRaw": a.created_at.isoformat() if a.created_at else None
        })

    # Dynamic Alert Type Distribution from DB
    type_counts = {}
    for a in all_alerts:
        formatted_type = a.alert_type.replace("_", " ").title()
        type_counts[formatted_type] = type_counts.get(formatted_type, 0) + 1

    color_palette = {
        "Stockout": "#D64545",
        "Stockout Risk": "#D64545",
        "Low Stock": "#E58A24",
        "Expiry Risk": "#D5A72C",
        "Demand Surge": "#177A5B",
        "Demand Spike": "#177A5B",
        "Supplier Delay": "#68716D",
        "Temperature Breach": "#9333EA",
        "Critical Shortage": "#D64545",
        "Overstock": "#3B82F6"
    }

    alerts_by_type = [
        {
            "name": t_name,
            "value": t_cnt,
            "color": color_palette.get(t_name, "#177A5B")
        }
        for t_name, t_cnt in type_counts.items() if t_cnt > 0
    ]

    # Dynamic Top Critical Alerts from DB
    top_crit = [a for a in all_alerts if a.severity == "critical" and a.status != "Resolved"][:4]
    top_critical_alerts = [
        {
            "product": a.product_name or a.sku,
            "sku": a.sku or "—",
            "warehouse": a.warehouse_id or "Network",
            "note": a.detail or "Critical stockout risk detected"
        }
        for a in top_crit
    ]

    # Dynamic Escalations Activity from escalations table
    esc_res = await db.execute(
        select(AlertEscalation).order_by(AlertEscalation.escalated_at.desc()).limit(6)
    )
    escalations = esc_res.scalars().all()
    
    recent_activity = [
        {
            "id": e.id,
            "text": f"Alert {e.alert_id} escalated to L{e.to_level} ({e.assigned_to})",
            "detail": e.reason or e.action_taken,
            "time": format_ist_datetime(e.escalated_at, fmt="%I:%M %p IST"),
            "status": e.status
        }
        for e in escalations
    ]
    if not recent_activity:
        # Fallback to recent transactions
        tx_res = await db.execute(select(InventoryTransaction).order_by(InventoryTransaction.timestamp.desc()).limit(4))
        txs = tx_res.scalars().all()
        recent_activity = [
            {
                "id": f"TX-{tx.id}",
                "text": f"{tx.transaction_type}: {tx.quantity:,} units {tx.sku} @ {tx.warehouse_id}",
                "detail": tx.reason or "Stock movement logged",
                "time": format_ist_datetime(tx.timestamp, fmt="%I:%M %p IST"),
                "status": "COMPLETED"
            }
            for tx in txs
        ]

    return {
        "counts": counts,
        "summary": counts,
        "alerts": filtered_alerts,
        "alerts_by_type": alerts_by_type,
        "root_causes": alerts_by_type,
        "top_critical_alerts": top_critical_alerts,
        "recent_activity": recent_activity
    }


@router.post("/{alert_id}/action")
@router.put("/{alert_id}")
async def handle_alert_action(
    alert_id: str,
    payload: AlertActionRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Executes real alert actions:
    - 'acknowledge': marks status as 'Acknowledged'
    - 'resolve': marks status as 'Resolved', records resolution escalation entry
    - 'escalate': increases escalation_level, creates AlertEscalation record
    """
    alert_res = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = alert_res.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert with ID '{alert_id}' not found.")

    action_type = payload.action.lower().strip()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if action_type in ["resolve", "mark resolved", "resolved"]:
        alert.status = "Resolved"
        alert.is_escalated = False
        alert.resolved_at = now_utc
        
        # Log resolution escalation
        esc = AlertEscalation(
            id=f"ESC-{int(now_utc.timestamp())}",
            alert_id=alert.id,
            from_level=alert.escalation_level,
            to_level=alert.escalation_level,
            assigned_to=payload.performed_by or "Lead Planner",
            reason=f"Alert resolved by {payload.performed_by or 'Planner'}",
            action_taken=payload.notes or "Operational corrective action executed.",
            sla_deadline=now_utc,
            escalated_at=now_utc,
            status="RESOLVED"
        )
        db.add(esc)

    elif action_type in ["acknowledge", "acknowledged"]:
        alert.status = "In Progress"
        
    elif action_type in ["escalate", "escalated"]:
        alert.escalation_level = min(3, alert.escalation_level + 1)
        alert.is_escalated = True
        
        esc = AlertEscalation(
            id=f"ESC-{int(now_utc.timestamp())}",
            alert_id=alert.id,
            from_level=alert.escalation_level - 1,
            to_level=alert.escalation_level,
            assigned_to=f"Tier-{alert.escalation_level} SCM Executive",
            reason=payload.notes or f"Manual escalation to Level {alert.escalation_level} by {payload.performed_by}",
            action_taken="Expedited executive decision requested.",
            sla_deadline=now_utc + timedelta(hours=4),
            escalated_at=now_utc,
            status="IN_PROGRESS"
        )
        db.add(esc)
    else:
        alert.status = payload.action.capitalize()

    await db.commit()

    # Broadcast WebSocket update
    await ws_manager.broadcast({
        "event": "ALERT_STATUS_UPDATED",
        "alert_id": alert.id,
        "status": alert.status,
        "action": action_type
    })

    return {
        "success": True,
        "id": alert.id,
        "new_status": alert.status,
        "message": f"Alert {alert.id} action '{action_type}' applied successfully."
    }


@router.get("/escalations")
async def get_escalations(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns full list of escalations from the database."""
    res = await db.execute(select(AlertEscalation).order_by(AlertEscalation.escalated_at.desc()))
    escs = res.scalars().all()
    return [
        {
            "id": e.id,
            "alertId": e.alert_id,
            "fromLevel": e.from_level,
            "toLevel": e.to_level,
            "assignedTo": e.assigned_to,
            "reason": e.reason,
            "actionTaken": e.action_taken,
            "status": e.status,
            "escalatedAt": e.escalated_at.strftime("%Y-%m-%d %H:%M") if e.escalated_at else "-",
            "slaDeadline": e.sla_deadline.strftime("%Y-%m-%d %H:%M") if e.sla_deadline else "-"
        }
        for e in escs
    ]

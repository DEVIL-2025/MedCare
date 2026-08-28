from datetime import UTC, datetime, timedelta, date
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.app.models.alert import Alert
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.models.replenishment import PurchaseOrder
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.notification import NotificationLog
from backend.app.config import settings


def _utc_now() -> datetime:
    """Return the current UTC time in the database's naive UTC format."""
    return datetime.now(UTC).replace(tzinfo=None)


class AlertEscalationEngine:
    """
    Alert Generation, Dynamic DB Synchronization, Lifecycle, and 3-Tier Shortage Escalation Engine.
    """

    @staticmethod
    async def create_alert(
        session: AsyncSession,
        alert_type: str,
        severity: str,
        sku: str,
        warehouse_id: str,
        detail: str,
        cause: Optional[str] = None,
        recommended_action: Optional[str] = None,
        owner: str = "Supply Chain Planner"
    ) -> Alert:
        """
        Creates an alert and computes initial escalation deadline based on severity.
        """
        today_dt = _utc_now()
        prod_res = await session.execute(select(Product).where(Product.sku == sku))
        prod = prod_res.scalars().first()
        prod_name = prod.name if prod else sku

        # Determine escalation SLA
        if severity == "critical":
            due_at = today_dt + timedelta(hours=settings.ESCALATION_CRITICAL_HOURS)
            level = 1
        elif severity == "warning":
            due_at = today_dt + timedelta(hours=settings.ESCALATION_HIGH_HOURS)
            level = 1
        else:
            due_at = today_dt + timedelta(hours=settings.ESCALATION_MEDIUM_HOURS)
            level = 1

        alert_id = f"ALT-{int(today_dt.timestamp() * 1000)}-{sku}-{warehouse_id}"
        alert = Alert(
            id=alert_id,
            alert_type=alert_type,
            severity=severity,
            sku=sku,
            product_name=prod_name,
            warehouse_id=warehouse_id,
            detail=detail,
            cause=cause,
            recommended_action=recommended_action,
            owner=owner,
            status="New",
            escalation_level=level,
            escalation_due_at=due_at,
            is_escalated=False,
            created_at=today_dt
        )
        session.add(alert)
        await session.flush()
        return alert

    @staticmethod
    async def sync_inventory_alerts(
        session: AsyncSession,
        sku: Optional[str] = None,
        warehouse_id: Optional[str] = None
    ) -> List[Alert]:
        """
        Dynamically synchronizes alerts in PostgreSQL with current live inventory & batch status:
        - If current_stock <= 0 -> generates/ensures active STOCKOUT alert (critical).
        - If current_stock < safety_stock -> generates/ensures active LOW_STOCK alert (critical).
        - If current_stock <= reorder_point -> generates/ensures active LOW_STOCK alert (warning).
        - If current_stock > reorder_point -> automatically resolves existing active stockout/low-stock alerts.
        - If batches expiring <= settings.EXPIRY_CRITICAL_DAYS -> generates/ensures active EXPIRY_RISK alert.
        """
        today = date.today()
        now = _utc_now()
        now_ms = int(now.timestamp() * 1000)

        # 1. Fetch matching active inventory items (active warehouses only)
        inv_query = (
            select(Inventory, Product)
            .join(Product, Inventory.sku == Product.sku)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(Product.is_active != False, Warehouse.is_active != False)
        )
        if sku:
            inv_query = inv_query.where(Inventory.sku == sku)
        if warehouse_id and warehouse_id != "All":
            inv_query = inv_query.where(Inventory.warehouse_id == warehouse_id)

        inv_res = await session.execute(inv_query)
        items = inv_res.all()

        # Bulk pre-fetch all existing active/relevant alerts, batches, active POs, and transfers
        all_alerts_res = await session.execute(select(Alert))
        alerts_by_node = {}
        for a in all_alerts_res.scalars().all():
            alerts_by_node.setdefault(f"{a.sku}_{a.warehouse_id}", []).append(a)

        all_batches_res = await session.execute(
            select(Batch).where(Batch.quantity > 0)
        )
        batches_by_node = {}
        for b in all_batches_res.scalars().all():
            batches_by_node.setdefault(f"{b.sku}_{b.warehouse_id}", []).append(b)

        # Pre-fetch active POs (Draft, Sent, In Transit, Approved)
        pos_res = await session.execute(
            select(PurchaseOrder).where(PurchaseOrder.status.in_(["Draft", "Sent", "In Transit", "Approved", "PENDING", "SENT", "IN TRANSIT"]))
        )
        pos_by_node = {}
        for po in pos_res.scalars().all():
            pos_by_node.setdefault(f"{po.sku}_{po.warehouse_id}", []).append(po)

        # Pre-fetch active Transfers (RECOMMENDED, APPROVED, IN_TRANSIT)
        trfs_res = await session.execute(
            select(InventoryTransfer).where(InventoryTransfer.status.in_(["RECOMMENDED", "APPROVED", "IN_TRANSIT", "Recommended", "Approved", "In Transit"]))
        )
        trfs_by_node = {}
        for trf in trfs_res.scalars().all():
            trfs_by_node.setdefault(f"{trf.sku}_{trf.destination_warehouse_id}", []).append(trf)

        modified_alerts = []
        counter = 0

        for inv, prod in items:
            counter += 1
            node_key = f"{inv.sku}_{inv.warehouse_id}"
            all_node_alerts = alerts_by_node.get(node_key, [])
            active_alerts = [a for a in all_node_alerts if a.status != "Resolved"]

            stockout_alerts = [a for a in active_alerts if a.alert_type in ["STOCKOUT", "Stockout", "STOCKOUT_RISK", "Stockout Risk"]]
            lowstock_alerts = [a for a in active_alerts if a.alert_type in ["LOW_STOCK", "Low Stock"]]
            expiry_alerts = [a for a in active_alerts if a.alert_type in ["EXPIRY_RISK", "Expiry Risk"]]

            active_pos = pos_by_node.get(node_key, [])
            active_trfs = trfs_by_node.get(node_key, [])
            is_order_in_flight = len(active_pos) > 0 or len(active_trfs) > 0 or (inv.inbound_stock or 0) > 0

            # If a Purchase Order or Transfer is created for this item, move the alert to the Resolved section!
            if is_order_in_flight and (inv.current_stock <= inv.reorder_point or inv.current_stock <= 0):
                ref_desc = ""
                if active_pos:
                    po_first = active_pos[0]
                    ref_desc = f"Purchase Order {po_first.id} created ({po_first.quantity:,} units from {po_first.supplier_name})"
                elif active_trfs:
                    trf_first = active_trfs[0]
                    ref_desc = f"FEFO Transfer {trf_first.id} initiated ({trf_first.quantity:,} units from {trf_first.source_warehouse_id})"
                else:
                    ref_desc = f"Inbound delivery of {inv.inbound_stock:,} units in transit"

                for a in stockout_alerts + lowstock_alerts:
                    a.status = "Resolved"
                    a.resolved_at = now
                    a.detail = f"Resolved: {ref_desc}. Expected to restore stock above threshold."
                    modified_alerts.append(a)

            # Condition 1: Total Stockout (0 units and no PO in flight)
            elif inv.current_stock <= 0:
                if not stockout_alerts:
                    new_alert = Alert(
                        id=f"ALT-{now_ms}-{counter}-{inv.sku}-{inv.warehouse_id}",
                        alert_type="STOCKOUT",
                        severity="critical",
                        sku=inv.sku,
                        product_name=prod.name,
                        warehouse_id=inv.warehouse_id,
                        detail=f"Stockout: {prod.name} ({inv.sku}) is completely out of stock (0 units) at {inv.warehouse_id}.",
                        cause=f"High dispensing velocity exhausted inventory buffer (Safety Stock: {inv.safety_stock:,}).",
                        recommended_action="Create emergency purchase order or initiate inter-DC transfer immediately.",
                        owner="Supply Chain Planner",
                        status="New",
                        escalation_level=1,
                        escalation_due_at=now + timedelta(hours=settings.ESCALATION_CRITICAL_HOURS),
                        is_escalated=False,
                        created_at=now
                    )
                    session.add(new_alert)
                    modified_alerts.append(new_alert)
                # Auto-resolve low-stock alert since it's now an absolute stockout
                for la in lowstock_alerts:
                    la.status = "Resolved"
                    la.resolved_at = now
                    modified_alerts.append(la)

            # Condition 2: Critical Low Stock (< Safety Stock)
            elif inv.current_stock < inv.safety_stock:
                # Auto-resolve stockout alert if stock is now > 0
                for sa in stockout_alerts:
                    sa.status = "Resolved"
                    sa.resolved_at = now
                    modified_alerts.append(sa)

                if not lowstock_alerts:
                    new_alert = Alert(
                        id=f"ALT-{now_ms}-{counter}-{inv.sku}-{inv.warehouse_id}",
                        alert_type="LOW_STOCK",
                        severity="critical",
                        sku=inv.sku,
                        product_name=prod.name,
                        warehouse_id=inv.warehouse_id,
                        detail=f"Critical Low Stock: {prod.name} ({inv.sku}) at {inv.current_stock:,} units in {inv.warehouse_id} is below safety buffer ({inv.safety_stock:,}).",
                        cause=f"Current stock covers {inv.days_of_cover} days vs safety buffer.",
                        recommended_action="Expedite procurement replenishment order.",
                        owner="Supply Chain Planner",
                        status="New",
                        escalation_level=1,
                        escalation_due_at=now + timedelta(hours=settings.ESCALATION_CRITICAL_HOURS),
                        is_escalated=False,
                        created_at=now
                    )
                    session.add(new_alert)
                    modified_alerts.append(new_alert)
                else:
                    for la in lowstock_alerts:
                        if la.severity != "critical" or la.status == "Resolved":
                            la.status = "New"
                            la.severity = "critical"
                            la.detail = f"Critical Low Stock: {prod.name} ({inv.sku}) at {inv.current_stock:,} units in {inv.warehouse_id} is below safety buffer ({inv.safety_stock:,})."
                            modified_alerts.append(la)

            # Condition 3: Warning Low Stock (<= Reorder Point)
            elif inv.current_stock <= inv.reorder_point:
                # Auto-resolve stockout alert
                for sa in stockout_alerts:
                    sa.status = "Resolved"
                    sa.resolved_at = now
                    modified_alerts.append(sa)

                if not lowstock_alerts:
                    new_alert = Alert(
                        id=f"ALT-{now_ms}-{counter}-{inv.sku}-{inv.warehouse_id}",
                        alert_type="LOW_STOCK",
                        severity="warning",
                        sku=inv.sku,
                        product_name=prod.name,
                        warehouse_id=inv.warehouse_id,
                        detail=f"Low Stock: {prod.name} ({inv.sku}) at {inv.current_stock:,} units in {inv.warehouse_id} is below reorder point ({inv.reorder_point:,}).",
                        cause=f"Cover at {inv.days_of_cover} days under active clinical demand.",
                        recommended_action="Review replenishment schedule or approve pending PO.",
                        owner="Supply Chain Planner",
                        status="New",
                        escalation_level=1,
                        escalation_due_at=now + timedelta(hours=settings.ESCALATION_HIGH_HOURS),
                        is_escalated=False,
                        created_at=now
                    )
                    session.add(new_alert)
                    modified_alerts.append(new_alert)
                else:
                    for la in lowstock_alerts:
                        if la.severity != "warning" or la.status == "Resolved":
                            la.status = "New"
                            la.severity = "warning"
                            la.detail = f"Low Stock: {prod.name} ({inv.sku}) at {inv.current_stock:,} units in {inv.warehouse_id} is below reorder point ({inv.reorder_point:,})."
                            modified_alerts.append(la)

            # Condition 4: Healthy Stock (> Reorder Point) -> Auto-Resolve Deficit Alerts!
            else:
                for a in stockout_alerts + lowstock_alerts:
                    a.status = "Resolved"
                    a.resolved_at = now
                    a.detail = f"Resolved: Stock restored to {inv.current_stock:,} units ({inv.days_of_cover} days of cover)."
                    modified_alerts.append(a)

            # Condition 5: Batch Expiry Check
            batches = batches_by_node.get(node_key, [])
            expiry_threshold_days = settings.EXPIRY_CRITICAL_DAYS
            near_expiry_batches = [b for b in batches if (b.expiry_date - today).days <= expiry_threshold_days]

            if near_expiry_batches:
                earliest_b = min(near_expiry_batches, key=lambda b: b.expiry_date)
                d_exp = (earliest_b.expiry_date - today).days
                tot_exp_qty = sum(b.quantity for b in near_expiry_batches)
                if not expiry_alerts:
                    new_exp_alert = Alert(
                        id=f"ALT-{now_ms}-{counter}-EXP-{inv.sku}-{inv.warehouse_id}",
                        alert_type="EXPIRY_RISK",
                        severity="critical" if d_exp <= (expiry_threshold_days // 2) else "warning",
                        sku=inv.sku,
                        product_name=prod.name,
                        warehouse_id=inv.warehouse_id,
                        detail=f"Expiry Risk: Batch {earliest_b.id} ({tot_exp_qty:,} units) expires in {d_exp} days ({earliest_b.expiry_date.strftime('%d %b %Y')}).",
                        cause="FEFO near-expiry threshold reached.",
                        recommended_action="Execute FEFO dispatch or inter-DC transfer to high-velocity DC.",
                        owner="Quality Assurance Lead",
                        status="New",
                        escalation_level=1,
                        escalation_due_at=now + timedelta(hours=settings.ESCALATION_HIGH_HOURS),
                        is_escalated=False,
                        created_at=now
                    )
                    session.add(new_exp_alert)
                    modified_alerts.append(new_exp_alert)
            else:
                # All batches healthy -> auto-resolve any active expiry alerts
                for ea in expiry_alerts:
                    ea.status = "Resolved"
                    ea.resolved_at = now
                    ea.detail = f"Resolved: All active batches exceed {expiry_threshold_days}-day expiry threshold."
                    modified_alerts.append(ea)

        await session.flush()
        return modified_alerts

    @staticmethod
    async def advance_alert_status(
        session: AsyncSession,
        alert_id: str,
        action: str,  # acknowledge, progress, resolve, escalate
        performed_by: str = "Planner"
    ) -> Alert:
        """Advances the status lifecycle or escalates the alert."""
        res = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = res.scalars().first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")

        now = _utc_now()
        act = action.lower()

        if act == "acknowledge":
            alert.status = "Acknowledged"
            alert.acknowledged_at = now
        elif act == "progress":
            alert.status = "In Progress"
        elif act == "resolve":
            alert.status = "Resolved"
            alert.resolved_at = now
        elif act == "escalate":
            alert.escalation_level = min(3, alert.escalation_level + 1)
            alert.is_escalated = True
            if alert.escalation_level == 2:
                alert.owner = "SCM Manager"
                alert.escalation_due_at = now + timedelta(hours=12)
            elif alert.escalation_level == 3:
                alert.owner = "VP Supply Chain"
                alert.escalation_due_at = now + timedelta(hours=4)
        else:
            raise ValueError(f"Unknown alert action: {action}")

        await session.flush()
        return alert

    @staticmethod
    async def check_and_escalate_overdue(session: AsyncSession) -> List[Alert]:
        """
        Automated cron/worker task checking for alerts exceeding their SLA deadline.
        """
        now = _utc_now()
        res = await session.execute(
            select(Alert).where(
                and_(
                    Alert.status.in_(["New", "Acknowledged"]),
                    Alert.escalation_due_at < now,
                    Alert.escalation_level < 3
                )
            )
        )
        overdue_alerts = list(res.scalars().all())

        for a in overdue_alerts:
            a.escalation_level += 1
            a.is_escalated = True
            if a.escalation_level == 2:
                a.owner = "SCM Manager"
                a.escalation_due_at = now + timedelta(hours=12)
            elif a.escalation_level == 3:
                a.owner = "VP Supply Chain"
                a.escalation_due_at = now + timedelta(hours=4)

        await session.flush()
        return overdue_alerts

import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.risk_engine import RiskEngine
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_e1_end_to_end_pipeline():
    """
    E1 End-to-End Test:
    Sale Transaction
    → Inventory Updated
    → Low Stock Status
    → Risk Recalculated
    → Alert Generated
    → Notification Logged
    """
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from backend.app.models.inventory import Inventory
        res = await session.execute(select(Inventory).where(Inventory.sku == "A-2381", Inventory.warehouse_id == "DEL-02"))
        initial_inv = res.scalars().first()
        prev_stock = initial_inv.current_stock if initial_inv else 1000
        sale_qty = max(100, int(prev_stock - 50)) if prev_stock > 50 else int(prev_stock * 0.8)

        # 1. Execute Sale on A-2381 in DEL-02
        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku="A-2381",
            warehouse_id="DEL-02",
            quantity=sale_qty,
            reference_id="E2E-SALE-001",
            performed_by="AutomatedE2ETest"
        )
        assert inv.current_stock == prev_stock - sale_qty
        assert inv.status in ["LOW_STOCK", "CRITICAL", "OUT_OF_STOCK"]

        # 2. Risk Recalculation
        risk = await RiskEngine.evaluate_inventory_risk(session, "A-2381", "DEL-02")
        assert risk is not None
        assert risk.stockout_risk_level in ["critical", "high"]
        assert risk.days_of_cover < 15.0

        # 3. Alert Generation
        alert = await AlertEscalationEngine.create_alert(
            session=session,
            alert_type="LOW_STOCK",
            severity="critical",
            sku="A-2381",
            warehouse_id="DEL-02",
            detail=f"Stock for A-2381 in DEL-02 dropped to {inv.current_stock}, below safety threshold.",
            cause="Large bulk sale of 400 units."
        )
        assert alert.id is not None
        assert alert.severity == "critical"

        # 4. Multi-Channel Notification
        notif = await NotificationService.dispatch_notification(
            session=session,
            channel="EMAIL",
            recipient="aditi.rao@medcarepharma.com",
            alert_id=alert.id,
            subject=f"[CRITICAL] Low Stock Alert: A-2381 at DEL-02",
            message=f"Stock has dropped to {inv.current_stock} units ({risk.days_of_cover} days cover)."
        )
        assert notif.status == "DELIVERED"
        await session.rollback()

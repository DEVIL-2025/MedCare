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
        # 1. Execute Sale of 80 units on P-1042 in BLR-01 (Current stock = 180 -> 100)
        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku="P-1042",
            warehouse_id="BLR-01",
            quantity=80,
            reference_id="E2E-SALE-001",
            performed_by="AutomatedE2ETest"
        )
        assert inv.current_stock == 100
        assert inv.status in ["LOW_STOCK", "CRITICAL"]

        # 2. Risk Recalculation
        risk = await RiskEngine.evaluate_inventory_risk(session, "P-1042", "BLR-01")
        assert risk is not None
        assert risk.stockout_risk_level in ["critical", "high"]
        assert risk.days_of_cover < 10.0

        # 3. Alert Generation
        alert = await AlertEscalationEngine.create_alert(
            session=session,
            alert_type="LOW_STOCK",
            severity="critical",
            sku="P-1042",
            warehouse_id="BLR-01",
            detail=f"Stock for P-1042 in BLR-01 dropped to {inv.current_stock}, below safety threshold.",
            cause="Large bulk sale of 80 units."
        )
        assert alert.id is not None
        assert alert.severity == "critical"

        # 4. Multi-Channel Notification
        notif = await NotificationService.dispatch_notification(
            session=session,
            channel="EMAIL",
            recipient="aditi.rao@medcarepharma.com",
            alert_id=alert.id,
            subject=f"[CRITICAL] Low Stock Alert: P-1042 at BLR-01",
            message=f"Stock has dropped to {inv.current_stock} units ({risk.days_of_cover} days cover)."
        )
        assert notif.status == "DELIVERED"
        await session.rollback()

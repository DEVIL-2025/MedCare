import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
from backend.app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_alert_creation_and_escalation_deadline():
    async with AsyncSessionLocal() as session:
        alert = await AlertEscalationEngine.create_alert(
            session=session,
            alert_type="LOW_STOCK",
            severity="critical",
            sku="P-1042",
            warehouse_id="BLR-01",
            detail="Stock below safety threshold",
            cause="Sales surge",
            recommended_action="Procure 8,000 units"
        )
        assert alert.status == "New"
        assert alert.escalation_level == 1
        assert alert.escalation_due_at is not None

        # Advance status
        ack_alert = await AlertEscalationEngine.advance_alert_status(
            session=session,
            alert_id=alert.id,
            action="acknowledge"
        )
        assert ack_alert.status == "Acknowledged"

        # Resolve status
        resolved_alert = await AlertEscalationEngine.advance_alert_status(
            session=session,
            alert_id=alert.id,
            action="resolve"
        )
        assert resolved_alert.status == "Resolved"
        assert resolved_alert.severity == "critical"  # Preserves original severity
        await session.rollback()


@pytest.mark.asyncio
async def test_multi_channel_notification_dispatch():
    async with AsyncSessionLocal() as session:
        log = await NotificationService.dispatch_notification(
            session=session,
            channel="EMAIL",
            recipient="test@medcarepharma.com",
            alert_id="ALT-TEST-001",
            subject="Test Alert",
            message="Test message body"
        )
        assert log.channel == "EMAIL"
        assert log.status == "DELIVERED"
        await session.rollback()

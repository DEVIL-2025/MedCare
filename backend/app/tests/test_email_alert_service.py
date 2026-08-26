import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_

from backend.app.database import AsyncSessionLocal
from backend.app.config import settings
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.notification import NotificationLog
from backend.app.models.settings import SystemSetting
from backend.app.services.email_service import EmailService
from backend.app.services.email_alert_service import EmailAlertService, trigger_async_low_stock_check


@pytest.mark.asyncio
async def test_consolidated_digest_html_rendering():
    sample_items = [
        {
            "sku": "P-1042",
            "product_name": "Paracetamol 500mg",
            "category": "Analgesics",
            "warehouse_id": "MUM-01",
            "warehouse_name": "Mumbai Central DC",
            "warehouse_location": "Bhiwandi, Mumbai",
            "current_stock": 150,
            "available_stock": 150,
            "reorder_point": 450,
            "safety_stock": 180,
            "deficit": 300,
            "status": "LOW_STOCK"
        },
        {
            "sku": "A-2001",
            "product_name": "Amoxicillin 500mg",
            "category": "Antibiotics",
            "warehouse_id": "BLR-01",
            "warehouse_name": "Bangalore Central DC",
            "warehouse_location": "Peenya, Bengaluru",
            "current_stock": 40,
            "available_stock": 40,
            "reorder_point": 200,
            "safety_stock": 80,
            "deficit": 160,
            "status": "CRITICAL"
        }
    ]

    html = EmailAlertService.render_consolidated_digest_html(
        items=sample_items,
        frontend_url="http://localhost:5173"
    )
    assert "Consolidated Low-Stock Digest" in html
    assert "2 ITEMS FLAGGED" in html
    assert "Paracetamol 500mg" in html
    assert "Amoxicillin 500mg" in html
    assert "MUM-01" in html
    assert "BLR-01" in html
    assert "-460" in html  # Total deficit: 300 + 160 = 460
    assert "http://localhost:5173/replenishment" in html
    assert "MedCare Pharma SCM Control Tower" in html


@pytest.mark.asyncio
async def test_email_service_resend_mock():
    with patch("backend.app.config.settings.RESEND_API_KEY", "re_test_mock_key"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "resend-msg-12345"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            res = await EmailService.send_email(
                to=["planner@medcarepharma.com"],
                subject="[ALERT] Consolidated Low Stock Digest",
                html_body="<p>Test</p>"
            )
            assert res["status"] == "SENT"
            assert res["provider"] == "resend"
            assert res["id"] == "resend-msg-12345"
            assert mock_post.called


@pytest.mark.asyncio
async def test_consolidated_low_stock_detection_and_cooldown():
    async with AsyncSessionLocal() as session:
        # Ensure recipient is configured in settings
        setting_res = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "alert_recipient_email")
        )
        row = setting_res.scalar_one_or_none()
        if row:
            row.value = "test_planner@medcarepharma.com"
        else:
            session.add(SystemSetting(key="alert_recipient_email", value="test_planner@medcarepharma.com"))
        await session.commit()

        # Find active inventory item for testing
        inv_res = await session.execute(
            select(Inventory, Product, Warehouse)
            .join(Product, Inventory.sku == Product.sku)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .where(Warehouse.is_active != False, Product.is_active != False)
            .limit(1)
        )
        item = inv_res.first()
        assert item is not None
        inv, prod, wh = item

        # Force inventory to be below reorder point for test
        original_stock = inv.current_stock
        inv.current_stock = max(10, inv.reorder_point - 50)
        await session.commit()

        try:
            # 1. First run: Should dispatch 1 consolidated digest
            digests = await EmailAlertService.check_and_dispatch_low_stock_email_alerts(
                session=session,
                target_sku=inv.sku,
                target_warehouse_id=inv.warehouse_id,
                force_ignore_cooldown=False
            )
            assert len(digests) == 1
            first_digest = digests[0]
            assert "Consolidated Low Stock Digest" in first_digest["digest_subject"]
            assert first_digest["item_count"] >= 1
            assert first_digest["delivery_status"] in ["SENT", "SIMULATED", "PARTIAL", "FAILED"]

            # Verify audit log in NotificationLog table
            log_res = await session.execute(
                select(NotificationLog).where(
                    and_(
                        NotificationLog.channel == "EMAIL",
                        NotificationLog.subject.like("%Consolidated Low Stock Digest%")
                    )
                ).order_by(NotificationLog.id.desc())
            )
            log = log_res.scalars().first()
            assert log is not None
            assert log.recipient != ""

            # 2. Second run: Item in 24h cooldown should produce empty digest list if sent
            # If the first run succeeded, cooldown suppresses it
            if first_digest["delivery_status"] in ["SENT", "DELIVERED"]:
                second_digests = await EmailAlertService.check_and_dispatch_low_stock_email_alerts(
                    session=session,
                    target_sku=inv.sku,
                    target_warehouse_id=inv.warehouse_id,
                    force_ignore_cooldown=False
                )
                assert len(second_digests) == 0

            # 3. Third run with force_ignore_cooldown=True: Dispatches again
            forced_digests = await EmailAlertService.check_and_dispatch_low_stock_email_alerts(
                session=session,
                target_sku=inv.sku,
                target_warehouse_id=inv.warehouse_id,
                force_ignore_cooldown=True
            )
            assert len(forced_digests) == 1

        finally:
            # Restore original stock
            inv.current_stock = original_stock
            await session.commit()


@pytest.mark.asyncio
async def test_low_stock_api_endpoint():
    from backend.app.routers.notifications import run_low_stock_email_check
    async with AsyncSessionLocal() as session:
        # Ensure recipient is set
        setting_res = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "alert_recipient_email")
        )
        row = setting_res.scalar_one_or_none()
        if row:
            row.value = "test_planner@medcarepharma.com"
        else:
            session.add(SystemSetting(key="alert_recipient_email", value="test_planner@medcarepharma.com"))
        await session.commit()

        res = await run_low_stock_email_check(force_ignore_cooldown=True, db=session)
        assert res["success"] is True
        assert "dispatched_count" in res
        assert "alerts" in res


def test_trigger_async_low_stock_check_non_blocking():
    # Should schedule background coroutine without error
    trigger_async_low_stock_check(sku="P-1042", warehouse_id="MUM-01")
    trigger_async_low_stock_check()

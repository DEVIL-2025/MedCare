import pytest
import pytest_asyncio
from backend.app.database import AsyncSessionLocal
from backend.app.engines.inventory_engine import InventoryEngine


@pytest.mark.asyncio
async def test_sale_transaction_and_deduction():
    async with AsyncSessionLocal() as session:
        # Fetch current stock before transaction
        from sqlalchemy import select
        from backend.app.models.inventory import Inventory
        res = await session.execute(select(Inventory).where(Inventory.sku == "A-2381", Inventory.warehouse_id == "DEL-02"))
        initial_inv = res.scalars().first()
        prev_stock = initial_inv.current_stock if initial_inv else 800

        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku="A-2381",
            warehouse_id="DEL-02",
            quantity=50,
            reference_id="TEST-SALE-001",
            performed_by="TestRunner"
        )
        assert tx.quantity == -50
        assert inv.current_stock == tx.new_stock
        assert inv.current_stock == prev_stock - 50
        await session.rollback()


@pytest.mark.asyncio
async def test_receipt_transaction_and_addition():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from backend.app.models.inventory import Inventory
        res = await session.execute(select(Inventory).where(Inventory.sku == "A-2381", Inventory.warehouse_id == "DEL-02"))
        initial_inv = res.scalars().first()
        prev_stock = initial_inv.current_stock if initial_inv else 800

        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="RECEIPT",
            sku="A-2381",
            warehouse_id="DEL-02",
            quantity=300,
            reference_id="TEST-RECEIPT-001",
            performed_by="TestRunner"
        )
        assert tx.quantity == 300
        assert inv.current_stock == tx.new_stock
        assert inv.current_stock == prev_stock + 300
        await session.rollback()


@pytest.mark.asyncio
async def test_insufficient_stock_validation():
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError) as exc:
            await InventoryEngine.process_transaction(
                session=session,
                transaction_type="SALE",
                sku="P-1042",
                warehouse_id="PAT-01",
                quantity=500,  # Far exceeds available (25 units)
                performed_by="TestRunner"
            )
        assert "Insufficient stock" in str(exc.value)
        await session.rollback()


@pytest.mark.asyncio
async def test_receipt_with_custom_expiry_and_alert_sync():
    from datetime import date, timedelta
    from sqlalchemy import select
    from backend.app.models.batch import Batch
    from backend.app.engines.alert_escalation_engine import AlertEscalationEngine
    from backend.app.models.alert import Alert

    custom_exp = (date.today() + timedelta(days=25)).strftime("%Y-%m-%d")
    batch_test_id = "BAT-TEST-EXP-001"

    async with AsyncSessionLocal() as session:
        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="RECEIPT",
            sku="A-2381",
            warehouse_id="DEL-02",
            quantity=200,
            batch_id=batch_test_id,
            expiry_date=custom_exp,
            reference_id="PO-TEST-EXP",
            performed_by="TestRunner"
        )
        assert tx.quantity == 200

        # Verify batch record in DB has the exact expiry date
        b_res = await session.execute(select(Batch).where(Batch.id == batch_test_id))
        batch = b_res.scalars().first()
        assert batch is not None
        assert batch.expiry_date.strftime("%Y-%m-%d") == custom_exp
        assert batch.status in ["CRITICAL", "NEAR_EXPIRY"]

        # Verify alert engine generates or updates an EXPIRY_RISK alert for this batch
        alerts = await AlertEscalationEngine.sync_inventory_alerts(session, sku="A-2381", warehouse_id="DEL-02")
        exp_alert_res = await session.execute(
            select(Alert).where(
                Alert.sku == "A-2381",
                Alert.warehouse_id == "DEL-02",
                Alert.alert_type == "EXPIRY_RISK"
            )
        )
        exp_alert = exp_alert_res.scalars().first()
        assert exp_alert is not None
        assert exp_alert.status == "New"
        assert custom_exp in exp_alert.detail or batch_test_id in exp_alert.detail
        await session.rollback()


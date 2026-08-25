import pytest
import pytest_asyncio
from backend.app.database import AsyncSessionLocal
from backend.app.engines.inventory_engine import InventoryEngine


@pytest.mark.asyncio
async def test_sale_transaction_and_deduction():
    async with AsyncSessionLocal() as session:
        # P-1042 in BLR-01 initial stock is 180
        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku="P-1042",
            warehouse_id="BLR-01",
            quantity=30,
            reference_id="TEST-SALE-001",
            performed_by="TestRunner"
        )
        assert tx.quantity == -30
        assert inv.current_stock == tx.new_stock
        assert inv.current_stock == 150
        assert inv.status == "LOW_STOCK"
        await session.rollback()


@pytest.mark.asyncio
async def test_receipt_transaction_and_addition():
    async with AsyncSessionLocal() as session:
        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="RECEIPT",
            sku="P-1042",
            warehouse_id="BLR-01",
            quantity=100,
            reference_id="TEST-RECEIPT-001",
            performed_by="TestRunner"
        )
        assert tx.quantity == 100
        assert inv.current_stock == 280
        assert inv.status == "HEALTHY"
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

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

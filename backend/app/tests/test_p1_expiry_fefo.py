import pytest
from datetime import date, timedelta
from backend.app.database import AsyncSessionLocal
from backend.app.engines.expiry_fefo_engine import ExpiryFEFOEngine


def test_batch_expiry_categorization():
    today = date(2026, 8, 24)
    
    cat_crit, _ = ExpiryFEFOEngine.categorize_batch_expiry(today + timedelta(days=20), today)
    assert cat_crit == "CRITICAL"

    cat_risk, _ = ExpiryFEFOEngine.categorize_batch_expiry(today + timedelta(days=60), today)
    assert cat_risk == "AT_RISK"

    cat_watch, _ = ExpiryFEFOEngine.categorize_batch_expiry(today + timedelta(days=120), today)
    assert cat_watch == "WATCH"

    cat_norm, _ = ExpiryFEFOEngine.categorize_batch_expiry(today + timedelta(days=365), today)
    assert cat_norm == "NORMAL"


@pytest.mark.asyncio
async def test_fefo_batch_allocation_order():
    async with AsyncSessionLocal() as session:
        allocations = await ExpiryFEFOEngine.allocate_fefo_batches(
            session=session,
            sku="P-1042",
            warehouse_id="MUM-01",
            required_quantity=200
        )
        assert len(allocations) > 0
        total_allocated = sum(a["allocated_quantity"] for a in allocations)
        assert total_allocated == 200
        # Earliest expiry allocated first
        if len(allocations) > 1:
            assert allocations[0]["days_to_expiry"] <= allocations[1]["days_to_expiry"]


@pytest.mark.asyncio
async def test_multi_batch_fefo_outbound_deduction():
    from backend.app.models.batch import Batch
    from backend.app.models.inventory import Inventory
    from backend.app.models.product import Product
    from backend.app.engines.inventory_engine import InventoryEngine
    from sqlalchemy import select

    today = date.today()
    sku = "TEST-FEFO-SKU"
    wh = "MUM-01"

    async with AsyncSessionLocal() as session:
        # Create test product master record
        prod = Product(
            sku=sku,
            name="Test FEFO Product",
            category="Antibiotics",
            unit="Strips",
            unit_cost=50.0,
            shelf_life_days=730,
            is_active=True
        )
        session.add(prod)

        # Create test product inventory
        inv = Inventory(
            sku=sku,
            warehouse_id=wh,
            current_stock=800,
            reserved_stock=0,
            inbound_stock=0,
            reorder_point=500,
            safety_stock=200,
            status="HEALTHY",
            risk_level="low",
            days_of_cover=30.0
        )
        session.add(inv)

        # Batch 1: Critical (expires in 20 days) -> 100 units
        b1 = Batch(
            id="BAT-FEFO-CRIT-20D",
            sku=sku,
            warehouse_id=wh,
            quantity=100,
            reserved_quantity=0,
            mfg_date=today - timedelta(days=300),
            expiry_date=today + timedelta(days=20),
            status="CRITICAL"
        )
        # Batch 2: Near Expiry (expires in 60 days) -> 200 units
        b2 = Batch(
            id="BAT-FEFO-NEAR-60D",
            sku=sku,
            warehouse_id=wh,
            quantity=200,
            reserved_quantity=0,
            mfg_date=today - timedelta(days=200),
            expiry_date=today + timedelta(days=60),
            status="NEAR_EXPIRY"
        )
        # Batch 3: Normal Safe (expires in 400 days) -> 500 units
        b3 = Batch(
            id="BAT-FEFO-NORM-400D",
            sku=sku,
            warehouse_id=wh,
            quantity=500,
            reserved_quantity=0,
            mfg_date=today - timedelta(days=50),
            expiry_date=today + timedelta(days=400),
            status="ACTIVE"
        )
        session.add_all([b1, b2, b3])
        await session.flush()

        # Execute Outbound Sale of 150 units without specifying batch_id (Pure FEFO)
        # Expected:
        # 1. 100 units deducted from b1 (expires in 20d) -> b1.quantity becomes 0 (DEPLETED)
        # 2. 50 units deducted from b2 (expires in 60d) -> b2.quantity becomes 150
        # 3. 0 units deducted from b3 (expires in 400d) -> b3.quantity remains 500
        tx, updated_inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku=sku,
            warehouse_id=wh,
            quantity=150,
            reference_id="TEST-FEFO-OUTBOUND",
            performed_by="TestRunner"
        )

        assert updated_inv.current_stock == 650
        assert b1.quantity == 0
        assert b1.status == "DEPLETED"
        assert b2.quantity == 150
        assert b3.quantity == 500

        # Now execute another Outbound Sale of 100 units
        # Expected:
        # 1. 100 units deducted from b2 (near expiry 60d) -> b2.quantity becomes 50
        # 2. b3 remains untouched at 500
        tx2, updated_inv2 = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku=sku,
            warehouse_id=wh,
            quantity=100,
            reference_id="TEST-FEFO-OUTBOUND-2",
            performed_by="TestRunner"
        )
        assert updated_inv2.current_stock == 550
        assert b2.quantity == 50
        assert b3.quantity == 500

        await session.rollback()


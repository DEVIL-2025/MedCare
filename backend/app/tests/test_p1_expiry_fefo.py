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

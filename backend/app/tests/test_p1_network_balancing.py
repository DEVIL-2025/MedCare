import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine


@pytest.mark.asyncio
async def test_network_balancing_transfer_discovery():
    async with AsyncSessionLocal() as session:
        transfers = await NetworkBalancingEngine.identify_network_transfers(session)
        assert len(transfers) > 0
        
        # Verify transfer candidates have positive savings
        for t in transfers:
            assert t.quantity > 0
            assert t.estimated_savings_inr >= 0
            assert t.source_warehouse_id != t.destination_warehouse_id
        await session.rollback()

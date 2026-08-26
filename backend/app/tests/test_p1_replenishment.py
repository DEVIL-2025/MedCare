import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.replenishment_engine import ReplenishmentEngine


@pytest.mark.asyncio
async def test_replenishment_recommendations_generation():
    async with AsyncSessionLocal() as session:
        recs = await ReplenishmentEngine.compute_recommendations(session)
        assert len(recs) > 0
        
        for r in recs:
            assert r.recommended_quantity >= 0
            assert r.recommended_frequency is not None
            assert r.decision_type in ["REPLENISH", "TRANSFER", "URGENT_REPLENISHMENT", "MONITOR"]
            assert r.reason_what is not None
            assert r.reason_why is not None
        await session.rollback()

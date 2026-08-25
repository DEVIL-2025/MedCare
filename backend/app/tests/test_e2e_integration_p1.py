import pytest
from backend.app.database import AsyncSessionLocal
from backend.app.engines.demand_sensing_engine import DemandSensingEngine
from backend.app.engines.risk_engine import RiskEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.engines.inventory_engine import InventoryEngine


@pytest.mark.asyncio
async def test_p1_end_to_end_flu_surge_and_transfer_pipeline():
    """
    P1 Primary Demonstration Scenario End-to-End Test:
    Flu Season Demand Surge (+60%) in Tier-2 DC (PAT-01)
    → Forecast Demand Rises
    → Stockout Risk Imminent in 3.5 Days
    → System Identifies Excess Near-Expiry Stock in MUM-01 (expires in 45 days)
    → Recommends FEFO Transfer MUM-01 -> PAT-01
    → Executes Transfer
    → Stockout Risk Resolved without New Procurement!
    """
    async with AsyncSessionLocal() as session:
        # 1. Demand Sensing Surge Detection on PAT-01
        f_data = await DemandSensingEngine.compute_sku_warehouse_forecast(
            session=session,
            sku="P-1042",
            warehouse_id="PAT-01",
            horizon_days=30
        )
        assert f_data["surge_detected"] is True
        assert f_data["surge_pct"] >= 25.0

        # 2. Risk Calculation shows Critical / High Stockout
        risk = await RiskEngine.evaluate_inventory_risk(session, "P-1042", "PAT-01")
        assert risk is not None
        assert risk.stockout_risk_level in ["critical", "high"]
        assert risk.days_of_cover <= 8.0

        # 3. Network Transfer Discovery identifies MUM-01 -> PAT-01 candidate
        transfers = await NetworkBalancingEngine.identify_network_transfers(session)
        matching_trf = next(
            (t for t in transfers if t.sku == "P-1042" and t.destination_warehouse_id == "PAT-01"),
            None
        )
        assert matching_trf is not None
        assert matching_trf.source_warehouse_id == "MUM-01"
        assert matching_trf.quantity >= 50

        # 4. Execute Transfer
        trf_qty = matching_trf.quantity
        tx_out, inv_src = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="TRANSFER_OUT",
            sku="P-1042",
            warehouse_id="MUM-01",
            quantity=trf_qty,
            reference_id="E2E-TRF-001"
        )
        tx_in, inv_dst = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="TRANSFER_IN",
            sku="P-1042",
            warehouse_id="PAT-01",
            quantity=trf_qty,
            reference_id="E2E-TRF-001"
        )

        # 5. Verify PAT-01 Stock restored
        assert inv_dst.current_stock == 25 + trf_qty
        new_risk = await RiskEngine.evaluate_inventory_risk(session, "P-1042", "PAT-01")
        assert new_risk is not None
        assert new_risk.days_of_cover > 3.0
        assert inv_dst.status in ["HEALTHY", "LOW_STOCK"]
        await session.rollback()

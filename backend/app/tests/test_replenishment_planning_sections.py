import pytest
from datetime import date, timedelta, datetime, timezone
from sqlalchemy import select

from backend.app.database import AsyncSessionLocal
from backend.app.routers.replenishment import get_replenishment_overview, get_fefo_batches, approve_recommendation
from backend.app.routers.transfers import execute_transfer
from backend.app.models.replenishment import ReplenishmentRecommendation, PurchaseOrder
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.inventory import Inventory
from backend.app.models.batch import Batch
from backend.app.utils.timezone import get_today_ist


@pytest.mark.asyncio
async def test_section_1_replenishment_recommendations():
    async with AsyncSessionLocal() as session:
        overview = await get_replenishment_overview(db=session)
        assert "recommendations" in overview
        recs = overview["recommendations"]
        assert isinstance(recs, list)

        if len(recs) > 0:
            rec = recs[0]
            assert "id" in rec
            assert "sku" in rec
            assert "warehouse" in rec
            assert "recommendedQty" in rec
            assert "priority" in rec
            assert "reasonWhat" in rec
            assert "reasonWhy" in rec
            assert "decisionType" in rec

        await session.rollback()


@pytest.mark.asyncio
async def test_section_2_transfers_and_fefo_balancing_and_explorer():
    async with AsyncSessionLocal() as session:
        overview = await get_replenishment_overview(db=session)
        assert "transfer_opportunities" in overview
        trfs = overview["transfer_opportunities"]
        assert isinstance(trfs, list)

        for t in trfs:
            assert "id" in t
            assert "sku" in t
            assert "from" in t
            assert "to" in t
            assert t["from"] != t["to"]
            assert "quantity" in t
            assert t["quantity"] > 0
            assert "savings" in t

        # Test FEFO explorer endpoint
        fefo_data = await get_fefo_batches(sku="P-1042", warehouse_id="MUM-01", required_qty=100, db=session)
        assert "allocations" in fefo_data
        allocs = fefo_data["allocations"]
        assert isinstance(allocs, list)
        for a in allocs:
            assert a["sku"] == "P-1042"
            assert a["warehouse_id"] == "MUM-01"
            assert a["days_to_expiry"] > 0
            assert a["available_quantity"] > 0

        await session.rollback()


@pytest.mark.asyncio
async def test_section_3_fefo_transfer_execution_and_history():
    async with AsyncSessionLocal() as session:
        # Create a test transfer to execute
        today = get_today_ist()
        trf_id = "TEST-TRF-EXEC-001"
        
        # Verify source batch exists
        b_res = await session.execute(
            select(Batch).where(Batch.sku == "P-1042", Batch.warehouse_id == "MUM-01", Batch.quantity > 50)
        )
        batch = b_res.scalars().first()
        batch_id = batch.id if batch else None

        test_trf = InventoryTransfer(
            id=trf_id,
            sku="P-1042",
            source_warehouse_id="MUM-01",
            destination_warehouse_id="PAT-01",
            batch_id=batch_id,
            quantity=25,
            available_at_source=100,
            transfer_lead_time_days=3,
            estimated_savings_inr=1500.0,
            reason="Test FEFO balancing transfer",
            status="RECOMMENDED"
        )
        session.add(test_trf)
        await session.flush()

        # Execute transfer
        res = await execute_transfer(id=trf_id, db=session)
        assert res["success"] is True

        # Verify it appears in fefo_transfer_history
        overview = await get_replenishment_overview(db=session)
        history = overview["fefo_transfer_history"]
        matching_hist = next((h for h in history if h["id"] == trf_id), None)
        assert matching_hist is not None
        assert matching_hist["sku"] == "P-1042"
        assert matching_hist["from"] == "MUM-01"
        assert matching_hist["to"] == "PAT-01"
        assert matching_hist["quantity"] == 25

        await session.rollback()


@pytest.mark.asyncio
async def test_section_4_purchase_orders_and_approval_flow():
    async with AsyncSessionLocal() as session:
        today = get_today_ist()
        
        # Create a test recommendation
        rec_id = "TEST-REC-PO-001"
        test_rec = ReplenishmentRecommendation(
            id=rec_id,
            sku="P-1042",
            warehouse_id="MUM-01",
            current_stock=100,
            forecast_demand_30d=500.0,
            safety_stock=150,
            recommended_quantity=200,
            recommended_frequency="Every 14 days",
            next_review_date=today + timedelta(days=14),
            decision_type="REPLENISH",
            preferred_source="HealthGen Pharma",
            estimated_cost_inr=20000.0,
            priority="high",
            reason_what="Procure 200 units",
            reason_why="Stock below target",
            status="PENDING"
        )
        session.add(test_rec)
        await session.flush()

        # Approve recommendation
        appr_res = await approve_recommendation(rec_id=rec_id, db=session)
        assert appr_res["success"] is True
        assert appr_res["status"] == "APPROVED"
        assert appr_res["po_id"] is not None

        # Verify PO is in purchase_orders overview
        overview = await get_replenishment_overview(db=session)
        pos = overview["purchase_orders"]
        matching_po = next((po for po in pos if po["id"] == appr_res["po_id"]), None)
        assert matching_po is not None
        assert matching_po["sku"] == "P-1042"
        assert matching_po["warehouse"] == "MUM-01"
        assert matching_po["quantity"] == 200

        await session.rollback()

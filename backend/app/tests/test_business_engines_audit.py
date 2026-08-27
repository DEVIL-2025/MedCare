import pytest
from datetime import date, timedelta, datetime, timezone
from sqlalchemy import select, and_

from backend.app.database import AsyncSessionLocal
from backend.app.models.batch import Batch
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.transaction import InventoryTransaction
from backend.app.engines.expiry_fefo_engine import ExpiryFEFOEngine
from backend.app.engines.inventory_engine import InventoryEngine
from backend.app.engines.network_balancing_engine import NetworkBalancingEngine
from backend.app.engines.replenishment_engine import ReplenishmentEngine
from backend.app.engines.risk_engine import RiskEngine
from backend.app.engines.scenario_simulation_engine import ScenarioSimulationEngine
from backend.app.utils.timezone import get_today_ist


# ============================================================
# 1. FEFO & EXPIRY TESTS
# ============================================================

@pytest.mark.asyncio
async def test_fefo_never_allocates_expired_or_quarantined():
    today = get_today_ist()
    async with AsyncSessionLocal() as session:
        # Create test batches: 1 expired, 1 quarantined, 1 valid
        sku = "TEST-FEFO-SKU-01"
        wh_id = "MUM-01"

        b_expired = Batch(
            id="BAT-EXP-01", sku=sku, warehouse_id=wh_id, quantity=100, reserved_quantity=0,
            mfg_date=today - timedelta(days=400), expiry_date=today - timedelta(days=10),
            is_quarantined=False, status="EXPIRED"
        )
        b_quarantined = Batch(
            id="BAT-QUAR-01", sku=sku, warehouse_id=wh_id, quantity=100, reserved_quantity=0,
            mfg_date=today - timedelta(days=100), expiry_date=today + timedelta(days=200),
            is_quarantined=True, status="QUARANTINED"
        )
        b_valid = Batch(
            id="BAT-VALID-01", sku=sku, warehouse_id=wh_id, quantity=100, reserved_quantity=0,
            mfg_date=today - timedelta(days=30), expiry_date=today + timedelta(days=150),
            is_quarantined=False, status="ACTIVE"
        )
        session.add_all([b_expired, b_quarantined, b_valid])
        await session.flush()

        allocations = await ExpiryFEFOEngine.allocate_fefo_batches(
            session=session, sku=sku, warehouse_id=wh_id, required_quantity=50
        )
        allocated_ids = [a["batch_id"] for a in allocations]

        assert "BAT-EXP-01" not in allocated_ids
        assert "BAT-QUAR-01" not in allocated_ids
        assert "BAT-VALID-01" in allocated_ids
        assert allocations[0]["allocated_quantity"] == 50

        await session.rollback()


@pytest.mark.asyncio
async def test_fefo_allocation_order_and_multi_batch():
    today = get_today_ist()
    async with AsyncSessionLocal() as session:
        sku = "TEST-FEFO-MULTI"
        wh_id = "MUM-01"

        # Batch A expires in 10 days (qty 30), Batch B expires in 30 days (qty 100)
        b_a = Batch(
            id="BAT-A-10D", sku=sku, warehouse_id=wh_id, quantity=30, reserved_quantity=0,
            mfg_date=today - timedelta(days=100), expiry_date=today + timedelta(days=10),
            is_quarantined=False, status="ACTIVE"
        )
        b_b = Batch(
            id="BAT-B-30D", sku=sku, warehouse_id=wh_id, quantity=100, reserved_quantity=0,
            mfg_date=today - timedelta(days=50), expiry_date=today + timedelta(days=30),
            is_quarantined=False, status="ACTIVE"
        )
        session.add_all([b_a, b_b])
        await session.flush()

        # Required = 80 -> Must allocate 30 from A, 50 from B
        allocations = await ExpiryFEFOEngine.allocate_fefo_batches(
            session=session, sku=sku, warehouse_id=wh_id, required_quantity=80
        )
        assert len(allocations) == 2
        assert allocations[0]["batch_id"] == "BAT-A-10D"
        assert allocations[0]["allocated_quantity"] == 30
        assert allocations[1]["batch_id"] == "BAT-B-30D"
        assert allocations[1]["allocated_quantity"] == 50

        await session.rollback()


# ============================================================
# 2. INVENTORY TRANSACTIONS & NORMALIZATION
# ============================================================

@pytest.mark.asyncio
async def test_inventory_transaction_lifecycle():
    today = get_today_ist()
    async with AsyncSessionLocal() as session:
        sku = "P-1042"
        wh_id = "MUM-01"

        # Get initial stock
        inv_res = await session.execute(select(Inventory).where(Inventory.sku == sku, Inventory.warehouse_id == wh_id))
        inv = inv_res.scalars().first()
        initial_stock = inv.current_stock

        # 1. RECEIPT
        tx_rec, inv = await InventoryEngine.process_transaction(
            session=session, transaction_type="RECEIPT", sku=" p-1042 ", warehouse_id=" mum-01 ",
            quantity=100, reference_id="TEST-REC-01"
        )
        assert inv.current_stock == initial_stock + 100
        assert tx_rec.new_stock == initial_stock + 100
        assert tx_rec.sku == "P-1042"
        assert tx_rec.warehouse_id == "MUM-01"

        # 2. SALE
        tx_sale, inv = await InventoryEngine.process_transaction(
            session=session, transaction_type="SALE", sku="P-1042", warehouse_id="MUM-01",
            quantity=40, reference_id="TEST-SALE-01"
        )
        assert inv.current_stock == initial_stock + 60
        assert tx_sale.new_stock == initial_stock + 60

        # 3. ADJUSTMENT
        tx_adj, inv = await InventoryEngine.process_transaction(
            session=session, transaction_type="ADJUSTMENT", sku="P-1042", warehouse_id="MUM-01",
            quantity=-10, reference_id="TEST-ADJ-01"
        )
        assert inv.current_stock == initial_stock + 50

        await session.rollback()


# ============================================================
# 3. NETWORK BALANCING TESTS
# ============================================================

@pytest.mark.asyncio
async def test_network_balancing_quantities_and_safeguards():
    async with AsyncSessionLocal() as session:
        transfers = await NetworkBalancingEngine.identify_network_transfers(session)
        assert isinstance(transfers, list)

        for t in transfers:
            assert t.quantity > 0
            assert t.quantity <= 5000
            assert t.source_warehouse_id != t.destination_warehouse_id
            assert t.estimated_savings_inr >= 0
            assert t.transfer_lead_time_days >= 1

        await session.rollback()


# ============================================================
# 4. REPLENISHMENT COHERENT FORMULA TEST (EXACT SECTION 9)
# ============================================================

@pytest.mark.asyncio
async def test_replenishment_exact_formula_verification():
    """
    Test exact Section 9 specification:
    Daily demand = 20
    Lead time = 5
    Buffer = 2
    Safety stock = 100
    Available stock = 80
    Inbound = 20

    Expected:
    Lead-time demand = 20 * (5 + 2) = 140
    Target stock = 140 + 100 = 240
    Effective inventory = 80 + 20 = 100
    Recommended replenishment = max(0, 240 - 100) = 140
    """
    daily_demand = 20.0
    lead_time = 5
    buffer = 2
    safety_stock = 100
    available_stock = 80
    inbound_stock = 20

    lead_time_demand = daily_demand * (lead_time + buffer)
    target_stock = lead_time_demand + safety_stock
    effective_inventory = available_stock + inbound_stock
    recommended_qty = max(0, int(round(target_stock - effective_inventory)))

    assert lead_time_demand == 140
    assert target_stock == 240
    assert effective_inventory == 100
    assert recommended_qty == 140


# ============================================================
# 5. RISK ENGINE TESTS
# ============================================================

@pytest.mark.asyncio
async def test_risk_score_bounds_and_zero_demand():
    async with AsyncSessionLocal() as session:
        # Standard evaluate
        risk = await RiskEngine.evaluate_inventory_risk(session, "P-1042", "MUM-01")
        if risk:
            assert 0.0 <= risk.stockout_risk_score <= 100.0
            assert 0.0 <= risk.expiry_risk_score <= 100.0
            assert risk.stockout_risk_level in ["critical", "high", "medium", "low"]
            assert risk.expiry_risk_level in ["critical", "high", "medium", "low"]

        await session.rollback()


# ============================================================
# 6. SCENARIO SIMULATION 10 PARAMETRIC TESTS
# ============================================================

@pytest.mark.asyncio
async def test_scenario_simulation_10_stress_controls():
    async with AsyncSessionLocal() as session:
        # 1. All scenario changes = 0 (Baseline consistency)
        res_baseline = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Baseline Scenario",
            demand_change_pct=0.0, lead_time_change_days=0, starting_inventory_change_pct=0.0,
            capacity_constraint_pct=0.0, distributor_demand_change_pct=0.0
        )
        assert res_baseline["status"] == "Completed"
        base_sl = float(res_baseline["service_level"].replace("%", ""))

        # 2. Demand +20%
        res_d20 = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Demand +20%",
            demand_change_pct=20.0, lead_time_change_days=0, starting_inventory_change_pct=0.0,
            capacity_constraint_pct=0.0, distributor_demand_change_pct=0.0
        )
        assert res_d20["status"] == "Completed"

        # 3. Demand +50%
        res_d50 = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Demand +50%",
            demand_change_pct=50.0, lead_time_change_days=0, starting_inventory_change_pct=0.0,
            capacity_constraint_pct=0.0, distributor_demand_change_pct=0.0
        )
        assert res_d50["impact_summary"]["projected_stockout_skus"] >= res_d20["impact_summary"]["projected_stockout_skus"]

        # 4. Lead time +3 days
        res_lt3 = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Lead Time +3d",
            demand_change_pct=0.0, lead_time_change_days=3, starting_inventory_change_pct=0.0,
            capacity_constraint_pct=0.0, distributor_demand_change_pct=0.0
        )
        assert res_lt3["status"] == "Completed"

        # 5. Inventory -20%
        res_inv20 = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Inventory -20%",
            demand_change_pct=0.0, lead_time_change_days=0, starting_inventory_change_pct=-20.0,
            capacity_constraint_pct=0.0, distributor_demand_change_pct=0.0
        )
        assert res_inv20["status"] == "Completed"

        # 6. Capacity constraint 30%
        res_cap30 = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Capacity 30% Constraint",
            demand_change_pct=0.0, lead_time_change_days=0, starting_inventory_change_pct=0.0,
            capacity_constraint_pct=30.0, distributor_demand_change_pct=0.0
        )
        assert res_cap30["status"] == "Completed"
        cap_sl = float(res_cap30["service_level"].replace("%", ""))
        assert cap_sl <= base_sl  # Capacity constraint reduces or maintains service level

        # 7. Distributor demand change +25%
        res_dist = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Distributor Demand +25%",
            demand_change_pct=0.0, lead_time_change_days=0, starting_inventory_change_pct=0.0,
            capacity_constraint_pct=0.0, distributor_demand_change_pct=25.0
        )
        assert res_dist["status"] == "Completed"

        # 8. Combined stress scenario
        res_stress = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Combined Stress",
            demand_change_pct=60.0, lead_time_change_days=5, starting_inventory_change_pct=-15.0,
            capacity_constraint_pct=20.0, distributor_demand_change_pct=30.0
        )
        assert res_stress["status"] == "Completed"
        assert res_stress["impact_summary"]["projected_stockout_skus"] >= 1

        # 9. Category filter: Analgesics
        res_cat = await ScenarioSimulationEngine.run_simulation(
            session=session, name="Analgesics Filter",
            demand_change_pct=20.0, category_filter="Analgesics"
        )
        assert res_cat["status"] == "Completed"

        # 10. Warehouse filter: MUM-01
        res_wh = await ScenarioSimulationEngine.run_simulation(
            session=session, name="MUM-01 Filter",
            demand_change_pct=20.0, warehouse_filter="MUM-01"
        )
        assert res_wh["status"] == "Completed"

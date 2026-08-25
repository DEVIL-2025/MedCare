import asyncio
import httpx
import sys
from datetime import date
from httpx import ASGITransport
from backend.app.main import app
from backend.app.database import AsyncSessionLocal
from backend.app.engines.expiry_fefo_engine import ExpiryFEFOEngine
from backend.database.seed_fefo_test_data import seed_fefo_test_dataset
from sqlalchemy import text

sys.stdout.reconfigure(encoding='utf-8')


async def test_fefo_validation_pipeline():
    print("=================================================================")
    print("   TESTING FEFO VALIDATION PIPELINE & BATCH ALLOCATION ENGINE")
    print("=================================================================")

    # Step 0: Ensure fresh seed of FEFO validation dataset
    await seed_fefo_test_dataset()

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # ------------------------------------------------------------------
        # CRITERION 1 & 2: Initial FEFO Priority Ranking from PostgreSQL
        # ------------------------------------------------------------------
        print("\n[Criterion 1 & 2] Fetching initial FEFO batch allocation for FEFO-TEST-001 at WH-TEST-01...")
        res = await client.get("/api/replenishment/fefo-batches?sku=FEFO-TEST-001&warehouse_id=WH-TEST-01")
        assert res.status_code == 200
        allocations = res.json().get("allocations", [])
        
        print(f"  Retrieved {len(allocations)} eligible batches from PostgreSQL:")
        for idx, a in enumerate(allocations, 1):
            print(f"    Rank {idx}: Batch {a['batch_id']} | Expiry: {a['expiry_date']} | Qty: {a['available_quantity']} | Priority: {a['priority']}")

        # Verification:
        # FEFO-BATCH-EXP (expired 2026-07-01) must NOT be present
        # FEFO-BATCH-ZERO (quantity 0) must NOT be present
        # Initial ranking must be: FEFO-BATCH-A (2026-09-10) -> FEFO-BATCH-B (2026-10-15) -> FEFO-BATCH-C (2027-01-20)
        batch_ids = [a["batch_id"] for a in allocations]
        assert "FEFO-BATCH-EXP" not in batch_ids, "Expired batch FEFO-BATCH-EXP must NOT be eligible"
        assert "FEFO-BATCH-ZERO" not in batch_ids, "Zero quantity batch FEFO-BATCH-ZERO must NOT be eligible"
        assert batch_ids == ["FEFO-BATCH-A", "FEFO-BATCH-B", "FEFO-BATCH-C"], f"Expected ['FEFO-BATCH-A', 'FEFO-BATCH-B', 'FEFO-BATCH-C'] but got {batch_ids}"
        assert allocations[0]["batch_id"] == "FEFO-BATCH-A", "Earliest valid batch (FEFO-BATCH-A) must be ranked 1st"
        print("  --> [PASSED] Criteria 1 & 2: Expired and zero-quantity batches excluded; earliest valid batch ranked 1st.")

        # ------------------------------------------------------------------
        # CRITERION 3: Dynamic Re-ranking when Expiry Dates Change in PostgreSQL
        # ------------------------------------------------------------------
        print("\n[Criterion 3] Modifying expiry dates in PostgreSQL: setting FEFO-BATCH-B to expire on 2026-09-01 (before BATCH-A)...")
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE batches SET expiry_date = '2026-09-01' WHERE id = 'FEFO-BATCH-B'"))
            await s.commit()

        res2 = await client.get("/api/replenishment/fefo-batches?sku=FEFO-TEST-001&warehouse_id=WH-TEST-01")
        allocations2 = res2.json().get("allocations", [])
        batch_ids2 = [a["batch_id"] for a in allocations2]
        print(f"  Re-ranked batches after DB update: {batch_ids2}")
        assert batch_ids2[0] == "FEFO-BATCH-B", f"Expected FEFO-BATCH-B to become Rank 1, but got {batch_ids2[0]}"
        assert batch_ids2 == ["FEFO-BATCH-B", "FEFO-BATCH-A", "FEFO-BATCH-C"]
        print("  --> [PASSED] Criterion 3: FEFO ordering dynamically re-ranked based on PostgreSQL change.")

        # ------------------------------------------------------------------
        # CRITERION 4: Dynamic Exclusion when Batch Quantity Becomes Zero
        # ------------------------------------------------------------------
        print("\n[Criterion 4] Updating FEFO-BATCH-B quantity to 0 in PostgreSQL...")
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE batches SET quantity = 0 WHERE id = 'FEFO-BATCH-B'"))
            await s.commit()

        res3 = await client.get("/api/replenishment/fefo-batches?sku=FEFO-TEST-001&warehouse_id=WH-TEST-01")
        allocations3 = res3.json().get("allocations", [])
        batch_ids3 = [a["batch_id"] for a in allocations3]
        print(f"  Eligible batches after depleting BATCH-B: {batch_ids3}")
        assert "FEFO-BATCH-B" not in batch_ids3, "Depleted batch FEFO-BATCH-B must be dynamically excluded"
        assert batch_ids3[0] == "FEFO-BATCH-A", "FEFO-BATCH-A must now be Rank 1"
        print("  --> [PASSED] Criterion 4: Zero-quantity batch dynamically excluded.")

        # ------------------------------------------------------------------
        # CRITERION 5: Dynamic Fallback when Earliest Batch is Marked Expired
        # ------------------------------------------------------------------
        print("\n[Criterion 5] Marking FEFO-BATCH-A as expired (expiry: 2026-08-01) in PostgreSQL...")
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE batches SET expiry_date = '2026-08-01' WHERE id = 'FEFO-BATCH-A'"))
            await s.commit()

        res4 = await client.get("/api/replenishment/fefo-batches?sku=FEFO-TEST-001&warehouse_id=WH-TEST-01")
        allocations4 = res4.json().get("allocations", [])
        batch_ids4 = [a["batch_id"] for a in allocations4]
        print(f"  Eligible batches after FEFO-BATCH-A expired: {batch_ids4}")
        assert batch_ids4 == ["FEFO-BATCH-C"], f"Expected only ['FEFO-BATCH-C'], got {batch_ids4}"
        print("  --> [PASSED] Criterion 5: Next eligible valid batch (FEFO-BATCH-C) automatically becomes Rank 1.")

        # ------------------------------------------------------------------
        # CRITERION 6: Warehouse Isolation (Cross-Warehouse Integrity)
        # ------------------------------------------------------------------
        print("\n[Criterion 6] Checking warehouse isolation for WH-TEST-02...")
        res_wh2 = await client.get("/api/replenishment/fefo-batches?sku=FEFO-TEST-001&warehouse_id=WH-TEST-02")
        allocations_wh2 = res_wh2.json().get("allocations", [])
        batch_ids_wh2 = [a["batch_id"] for a in allocations_wh2]
        print(f"  Batches returned for WH-TEST-02: {batch_ids_wh2}")
        assert batch_ids_wh2 == ["FEFO-BATCH-WH2-A"], f"WH-TEST-02 must only contain its own batches, got {batch_ids_wh2}"
        assert allocations_wh2[0]["warehouse_id"] == "WH-TEST-02"
        print("  --> [PASSED] Criterion 6: Multi-warehouse isolation verified with 0 cross-contamination.")

        # ------------------------------------------------------------------
        # Engine Direct Allocation Verification
        # ------------------------------------------------------------------
        print("\n[Engine Verification] Testing direct ExpiryFEFOEngine.allocate_fefo_batches...")
        # Reset test dataset
        await seed_fefo_test_dataset()
        async with AsyncSessionLocal() as s:
            # Request 220 units: should allocate 100 from BATCH-A + 120 from BATCH-B (leaving 30 in BATCH-B)
            engine_allocs = await ExpiryFEFOEngine.allocate_fefo_batches(
                session=s,
                sku="FEFO-TEST-001",
                warehouse_id="WH-TEST-01",
                required_quantity=220
            )
            print(f"  Engine allocated batches for 220 units: {engine_allocs}")
            assert len(engine_allocs) == 2
            assert engine_allocs[0]["batch_id"] == "FEFO-BATCH-A"
            assert engine_allocs[0]["allocated_quantity"] == 100
            assert engine_allocs[1]["batch_id"] == "FEFO-BATCH-B"
            assert engine_allocs[1]["allocated_quantity"] == 120
            print("  --> [PASSED] Engine FEFO quantity breakdown operates with mathematical precision.")

    print("\n=================================================================")
    print("   ALL 7 FEFO VALIDATION CRITERIA PASSED WITH 100% SUCCESS")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(test_fefo_validation_pipeline())

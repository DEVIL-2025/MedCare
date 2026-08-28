import asyncio
import httpx
import sys
from httpx import ASGITransport
from backend.app.main import app
from backend.app.database import AsyncSessionLocal
from sqlalchemy import text

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")


async def test_e2e_approval_flow():
    print("=================================================================")
    print("   TESTING END-TO-END APPROVAL FLOW FOR SUPPLIER REPLENISHMENT")
    print("=================================================================")

    # 1. Prepare DB state: ensure REC-A-2381-DEL-02 is PENDING
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE replenishment_recommendations SET status = 'PENDING' WHERE id = 'REC-A-2381-DEL-02'"))
        # Clean up any test POs for A-2381
        await s.execute(text("DELETE FROM purchase_orders WHERE sku = 'A-2381' AND id LIKE 'PO-%'"))
        await s.commit()

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 2. Query Dashboard before approval
        print("\n[Step 1] Fetching GET /api/dashboard...")
        dash_res = await client.get("/api/dashboard?warehouse=DEL-02")
        assert dash_res.status_code == 200, f"Dashboard returned {dash_res.status_code}"
        dash_data = dash_res.json()
        rec = dash_data.get("executive_recommendation")
        print(f"  Executive Recommendation on Dashboard: {rec}")
        assert rec is not None, "Expected active executive recommendation"
        print(f"  --> [PASSED] Active recommendation '{rec['id']}' surfaced on Dashboard.")

        # 3. If top recommendation is REC-C-5562-DEL-02, approve it so REC-A-2381-DEL-02 takes the top spot
        if rec["id"] == "REC-C-5562-DEL-02":
            print("\n[Step 2a] Approving prior recommendation REC-C-5562-DEL-02...")
            await client.post("/api/replenishment/REC-C-5562-DEL-02/approve")
            dash_res2 = await client.get("/api/dashboard?warehouse=DEL-02")
            rec = dash_res2.json().get("executive_recommendation")
            print(f"  Next Executive Recommendation on Dashboard: {rec}")

        # Now test the Amoxicillin / HealthGen Pharma recommendation approval
        assert rec is not None
        assert rec["id"] == "REC-A-2381-DEL-02"
        assert rec["action_type"] == "replenishment"
        assert rec["from"] == "HealthGen Pharma"
        assert rec["to"] == "DEL-02"
        print("  --> [PASSED] Amoxicillin 250mg / HealthGen Pharma recommendation is now top active recommendation.")

        # 4. Approve Amoxicillin Recommendation (1-Click Action)
        print("\n[Step 3] Executing POST /api/replenishment/REC-A-2381-DEL-02/approve...")
        app_res = await client.post("/api/replenishment/REC-A-2381-DEL-02/approve")
        print(f"  Status Code: {app_res.status_code}")
        print(f"  Response Body: {app_res.json()}")
        assert app_res.status_code == 200
        assert app_res.json()["status"] == "APPROVED"
        print("  --> [PASSED] Supplier PO recommendation approved successfully on backend.")

        # 4. Verify PurchaseOrder in database
        print("\n[Step 3] Checking purchase_orders table in PostgreSQL...")
        async with AsyncSessionLocal() as s:
            po_res = await s.execute(text("SELECT id, sku, warehouse_id, supplier_name, quantity, status FROM purchase_orders WHERE sku = 'A-2381'"))
            pos = po_res.fetchall()
            print(f"  Found POs in DB: {pos}")
            assert len(pos) >= 1, "Expected at least 1 PO created in database"
            po = pos[0]
            assert po[1] == "A-2381"
            assert po[2] == "DEL-02"
            assert po[3] == "HealthGen Pharma"
            assert po[4] == 800
            assert po[5] == "APPROVED"
        print("  --> [PASSED] Real PurchaseOrder row persisted in PostgreSQL.")

        # 5. Query Dashboard after approval to verify card advancement
        print("\n[Step 4] Fetching GET /api/dashboard after approval...")
        dash_res_after = await client.get("/api/dashboard?warehouse=DEL-02")
        dash_data_after = dash_res_after.json()
        rec_after = dash_data_after.get("executive_recommendation")
        print(f"  Executive Recommendation after approval: {rec_after}")
        if rec_after:
            assert rec_after["id"] != "REC-A-2381-DEL-02", "Previous approved recommendation should not reappear"
            print(f"  --> [PASSED] Next recommendation '{rec_after['id']}' advanced smoothly.")
        else:
            print("  --> [PASSED] All recommendations completed; empty/cleared state returned.")

        # 6. Check Replenishment Overview tabs
        print("\n[Step 5] Fetching GET /api/replenishment overview...")
        repl_res = await client.get("/api/replenishment?warehouse=DEL-02")
        assert repl_res.status_code == 200
        repl_data = repl_res.json()
        pos_list = repl_data.get("purchase_orders", [])
        approved_list = repl_data.get("approved_orders", [])
        print(f"  Purchase Orders count: {len(pos_list)}")
        print(f"  Approved Orders count: {len(approved_list)}")
        matching_po = [p for p in pos_list if p["sku"] == "A-2381"]
        assert len(matching_po) > 0, "Approved PO should be listed in Purchase Orders tab"
        print(f"  Matching PO found: {matching_po[0]}")
        print("  --> [PASSED] Purchase order appears correctly in Replenishment tabs.")

    print("\n=================================================================")
    print("   END-TO-END APPROVAL TEST COMPLETED WITH 100% SUCCESS")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(test_e2e_approval_flow())

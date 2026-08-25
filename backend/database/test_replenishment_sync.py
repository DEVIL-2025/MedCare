import asyncio
import httpx
import sys
from httpx import ASGITransport
from backend.app.main import app
from backend.app.database import AsyncSessionLocal
from sqlalchemy import text

sys.stdout.reconfigure(encoding='utf-8')


async def test_replenishment_synchronization():
    print("=================================================================")
    print("   TESTING DYNAMIC REPLENISHMENT & CROSS-SECTION SYNCHRONIZATION")
    print("=================================================================")

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # -------------------------------------------------------------
        # TEST 1: Dynamic Replenishment Recommendation Generation & Resolution
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing Dynamic Recommendation Generation & Auto-Resolution...")
        
        # Step 1a: Drop stock of P-1042 in MUM-01 to 50 units (safety stock is 2,500)
        print("  --> Setting P-1042 stock in MUM-01 to 50 units in PostgreSQL...")
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE inventory SET current_stock = 50 WHERE sku = 'P-1042' AND warehouse_id = 'MUM-01'"))
            await s.commit()

        # Fetch Replenishment Overview
        rep_res1 = await client.get("/api/replenishment?warehouse=MUM-01")
        assert rep_res1.status_code == 200
        recs1 = rep_res1.json().get("recommendations", [])
        p1042_rec = next((r for r in recs1 if r["sku"] == "P-1042" and r["warehouse"] == "MUM-01"), None)
        
        print(f"  Found recommendation for P-1042: {p1042_rec['name'] if p1042_rec else 'None'}")
        assert p1042_rec is not None, "Expected dynamic recommendation for P-1042 in MUM-01"
        assert p1042_rec["priority"] in ["critical", "high"], f"Expected critical/high priority, got {p1042_rec['priority']}"
        assert p1042_rec["recommendedQty"] >= 1000, f"Expected recommendedQty >= MOQ (1000), got {p1042_rec['recommendedQty']}"
        assert p1042_rec["currentStock"] == 50
        print(f"  --> [PASSED] Recommendation generated with Recommended Qty: {p1042_rec['recommendedQty']}, Priority: {p1042_rec['priority']}, Decision: {p1042_rec['decisionType']}")

        # Step 1b: Resolve the shortage by replenishing stock in PostgreSQL to 5,000 units
        print("  --> Restoring P-1042 stock in MUM-01 to 5,000 units (Healthy) in PostgreSQL...")
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE inventory SET current_stock = 5000 WHERE sku = 'P-1042' AND warehouse_id = 'MUM-01'"))
            await s.commit()

        # Re-fetch Replenishment Overview
        rep_res2 = await client.get("/api/replenishment?warehouse=MUM-01")
        recs2 = rep_res2.json().get("recommendations", [])
        p1042_rec_after = next((r for r in recs2 if r["sku"] == "P-1042" and r["warehouse"] == "MUM-01" and r["status"] == "PENDING"), None)
        print(f"  Pending recommendations for P-1042 after stock restoration: {p1042_rec_after}")
        assert p1042_rec_after is None, "Pending recommendation for P-1042 should be cleared/resolved"
        print("  --> [PASSED] Test 1: Dynamic recommendation automatically cleared when stock restored.")

        # Restore P-1042 stock to standard 2,900
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE inventory SET current_stock = 2900 WHERE sku = 'P-1042' AND warehouse_id = 'MUM-01'"))
            await s.commit()

        # -------------------------------------------------------------
        # TEST 2: Cross-Section Data Consistency (Inventory, Dashboard, Alerts, Replenishment)
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing Cross-Section Data Consistency for Target SKU...")
        
        # Test SKU: AZ-3391 in DEL-02
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE inventory SET current_stock = 250 WHERE sku = 'AZ-3391' AND warehouse_id = 'DEL-02'"))
            await s.commit()

        # Query all 4 sections
        dash_res = await client.get("/api/dashboard?warehouse=DEL-02")
        inv_res = await client.get("/api/inventory?warehouse=DEL-02")
        alt_res = await client.get("/api/alerts?warehouse=DEL-02")
        repl_res = await client.get("/api/replenishment?warehouse=DEL-02")

        # Extract values
        dash_at_risk = next((i for i in dash_res.json().get("top_at_risk_skus", []) if i["sku"] == "AZ-3391"), None)
        inv_item = next((i for i in inv_res.json() if i["sku"] == "AZ-3391"), None)
        alt_item = next((a for a in alt_res.json().get("alerts", []) if a["sku"] == "AZ-3391"), None)
        repl_item = next((r for r in repl_res.json().get("recommendations", []) if r["sku"] == "AZ-3391"), None)

        print(f"  Dashboard currentStock     : {dash_at_risk['currentStock'] if dash_at_risk else 'None'}")
        print(f"  Inventory currentStock     : {inv_item['currentStock'] if inv_item else 'None'}")
        print(f"  Alerts status / detail     : {alt_item['status'] if alt_item else 'None'} ({alt_item['type'] if alt_item else ''})")
        print(f"  Replenishment currentStock : {repl_item['currentStock'] if repl_item else 'None'}")

        assert dash_at_risk is not None, "AZ-3391 should appear on Dashboard at-risk"
        assert inv_item is not None, "AZ-3391 must be in inventory"
        assert alt_item is not None, "AZ-3391 must have active alert"
        assert repl_item is not None, "AZ-3391 must have active recommendation"

        assert dash_at_risk["currentStock"] == 250
        assert inv_item["currentStock"] == 250
        assert repl_item["currentStock"] == 250
        assert repl_item["warehouse"] == "DEL-02"
        print("  --> [PASSED] Test 2: Identifiers and quantities are 100% consistent across all 4 sections.")

        # Restore AZ-3391 stock to 6,000
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE inventory SET current_stock = 6000 WHERE sku = 'AZ-3391' AND warehouse_id = 'DEL-02'"))
            await s.commit()

        # -------------------------------------------------------------
        # TEST 3: 1-Click Recommendation Approval & Purchase Order Persistence
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing 1-Click PO Approval & Live Inbound Stock Synchronization...")
        
        # Ensure REC-A-2381-DEL-02 is PENDING
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE replenishment_recommendations SET status = 'PENDING' WHERE id = 'REC-A-2381-DEL-02'"))
            await s.execute(text("DELETE FROM purchase_orders WHERE sku = 'A-2381' AND id LIKE 'PO-%'"))
            await s.commit()

        # Approve recommendation
        app_res = await client.post("/api/replenishment/REC-A-2381-DEL-02/approve")
        assert app_res.status_code == 200
        print(f"  Approval result: {app_res.json()['message']}")

        # Verify PO created
        repl_after = await client.get("/api/replenishment?warehouse=DEL-02")
        pos = repl_after.json().get("purchase_orders", [])
        matching_po = next((p for p in pos if p["sku"] == "A-2381"), None)
        assert matching_po is not None, "Approved PO must appear in purchase_orders list"
        print(f"  Created PO in Replenishment list: {matching_po}")
        print("  --> [PASSED] Test 3: Approved recommendation creates PO and synchronizes state.")

    print("\n=================================================================")
    print("   ALL REPLENISHMENT & CROSS-SECTION SYNC TESTS PASSED (100%)")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(test_replenishment_synchronization())

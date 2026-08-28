import asyncio
import sys
from datetime import date, datetime
from sqlalchemy import select, and_, update
import httpx
from httpx import ASGITransport

from backend.app.database import AsyncSessionLocal
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.models.replenishment import ReplenishmentRecommendation
from backend.app.models.alert import Alert
from backend.app.models.transaction import InventoryTransaction
from backend.app.main import app

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")


async def test_system_wide_alignment():
    print("=================================================================")
    print("   TESTING SYSTEM-WIDE DATA ALIGNMENT & DYNAMIC SYNCHRONIZATION")
    print("=================================================================")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # -------------------------------------------------------------
        # TEST 1: Internal Consumption & Executive Transaction Ledger
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing Internal Consumption & Transaction Ledger...")
        async with AsyncSessionLocal() as session:
            # Check starting stock for P-1042 in MUM-01
            inv_res = await session.execute(
                select(Inventory).where(and_(Inventory.sku == "P-1042", Inventory.warehouse_id == "MUM-01"))
            )
            inv = inv_res.scalars().first()
            start_stock = inv.current_stock if inv else 5000

        consume_payload = {
            "transaction_type": "CONSUMPTION",
            "sku": "P-1042",
            "warehouse_id": "MUM-01",
            "quantity": 150,
            "reason": "Internal Consumption by Emergency Clinical Ward: Clinical trial batch test",
            "performed_by": "QA Auditor"
        }
        res_tx = await client.post("/api/transactions", json=consume_payload)
        assert res_tx.status_code == 200, f"Transaction failed: {res_tx.text}"
        tx_data = res_tx.json()
        print(f"  --> Consumption transaction recorded: ID {tx_data.get('transaction_id')}")

        # Verify in Transactions API
        res_txs = await client.get("/api/transactions?warehouse=MUM-01")
        assert res_txs.status_code == 200
        recent_txs = res_txs.json()
        matching_tx = next((t for t in recent_txs if t["transactionType"] == "CONSUMPTION" and t["sku"] == "P-1042"), None)
        assert matching_tx is not None, "Consumption transaction not found in ledger"
        assert matching_tx["quantity"] == -150 or matching_tx["quantity"] == 150
        print(f"  --> [PASSED] Test 1: Real internal consumption of {matching_tx['name']} logged with dynamic DB audit trail.")

        # -------------------------------------------------------------
        # TEST 2: Inactive / Deactivated Warehouse Lifecycle Filtering
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing Deactivated Warehouse Filtering across all modules...")
        async with AsyncSessionLocal() as session:
            # Temporarily deactivate WH-TEST-02
            await session.execute(
                update(Warehouse).where(Warehouse.id == "WH-TEST-02").values(is_active=False, status="Decommissioned")
            )
            await session.commit()

        # Check Warehouses API
        res_wh = await client.get("/api/warehouses")
        wh_list = res_wh.json().get("overview", [])
        assert not any(w["id"] == "WH-TEST-02" for w in wh_list), "Decommissioned warehouse appeared in /api/warehouses"

        # Check Dashboard Regional DC Status
        res_dash = await client.get("/api/dashboard")
        dash_health = res_dash.json().get("warehouse_health", [])
        assert not any(w["id"] == "WH-TEST-02" for w in dash_health), "Decommissioned warehouse appeared in Dashboard DC status"

        # Check Replenishment API
        res_rep = await client.get("/api/replenishment")
        rep_recs = res_rep.json().get("recommendations", [])
        assert not any(r["warehouse"] == "WH-TEST-02" for r in rep_recs), "Decommissioned warehouse appeared in Replenishment"

        # Restore WH-TEST-02
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Warehouse).where(Warehouse.id == "WH-TEST-02").values(is_active=True, status="Healthy")
            )
            await session.commit()
        print("  --> [PASSED] Test 2: Inactive / deleted warehouses are strictly excluded across all modules.")

        # -------------------------------------------------------------
        # TEST 3: Replenishment & Stock Improvement Sync
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing Replenishment Stock Improvement Synchronization...")
        async with AsyncSessionLocal() as session:
            # Set stock low for AZ-3391 in DEL-02 to trigger replenishment
            await session.execute(
                update(Inventory).where(and_(Inventory.sku == "AZ-3391", Inventory.warehouse_id == "DEL-02")).values(current_stock=100)
            )
            await session.commit()

        res_rep_low = await client.get("/api/replenishment?warehouse=DEL-02")
        recs_low = res_rep_low.json().get("recommendations", [])
        rec_az = next((r for r in recs_low if r["sku"] == "AZ-3391"), None)
        assert rec_az is not None, "Replenishment recommendation not generated for low stock"
        print(f"  --> Generated recommendation for AZ-3391: Order {rec_az['recommendedQty']} units (Priority: {rec_az['priority']})")

        # Now improve stock in PostgreSQL
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Inventory).where(and_(Inventory.sku == "AZ-3391", Inventory.warehouse_id == "DEL-02")).values(current_stock=8000)
            )
            await session.commit()

        res_rep_high = await client.get("/api/replenishment?warehouse=DEL-02")
        recs_high = res_rep_high.json().get("recommendations", [])
        rec_az_resolved = next((r for r in recs_high if r["sku"] == "AZ-3391" and r["status"] == "PENDING"), None)
        assert rec_az_resolved is None, "Replenishment recommendation was not auto-resolved after stock restoration"
        print("  --> [PASSED] Test 3: Replenishment recommendation auto-cleared when stock improved.")

        # -------------------------------------------------------------
        # TEST 4: Alerts Dynamic Auto-Resolution
        # -------------------------------------------------------------
        print("\n[TEST 4] Testing Alerts Dynamic Auto-Resolution...")
        res_alerts = await client.get("/api/alerts?warehouse=DEL-02")
        alerts_del = res_alerts.json().get("alerts", [])
        stockout_az = next((a for a in alerts_del if a["sku"] == "AZ-3391" and a["status"] != "Resolved"), None)
        assert stockout_az is None, "Stale stockout alert remained after stock was replenished"
        print("  --> [PASSED] Test 4: Alerts auto-resolved with zero stale notifications remaining.")

        # -------------------------------------------------------------
        # TEST 5: Grounded AI Assistant Live Queries
        # -------------------------------------------------------------
        print("\n[TEST 5] Testing Grounded AI Supply Chain Assistant...")
        q_stock = await client.post("/api/assistant/chat", json={"query": "What is the stock of Paracetamol in MUM-01?"})
        assert q_stock.status_code == 200
        ans_stock = q_stock.json()
        print(f"  --> AI Stock Query Answer:\n{ans_stock['answer']}")
        assert "Paracetamol" in ans_stock["answer"] and "MUM-01" in ans_stock["answer"]

        q_fefo = await client.post("/api/assistant/chat", json={"query": "Which batches are expiring soon?"})
        assert q_fefo.status_code == 200
        ans_fefo = q_fefo.json()
        assert "FEFO Batch Dispatch Priority" in ans_fefo["answer"]
        print("  --> [PASSED] Test 5: AI Assistant answers grounded accurately in PostgreSQL.")

    print("\n=================================================================")
    print("   ALL SYSTEM-WIDE ALIGNMENT & DYNAMIC TESTS PASSED (100%)")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(test_system_wide_alignment())

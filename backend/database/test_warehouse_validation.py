import asyncio
import httpx
import sys
from backend.app.main import app
from httpx import ASGITransport

sys.stdout.reconfigure(encoding='utf-8')


async def test_warehouse_validation():
    print("=================================================================")
    print("   TESTING WAREHOUSE_ID VALIDATION & ERROR HANDLING")
    print("=================================================================")

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: Transaction with "All Warehouses"
        print("\n[Test 1] POST /api/transactions with warehouse_id = 'All Warehouses':")
        r1 = await client.post("/api/transactions", json={
            "transaction_type": "SALE",
            "sku": "P-1042",
            "warehouse_id": "All Warehouses",
            "quantity": 50,
            "reason": "Test All Warehouses insertion"
        })
        print(f"  Status Code: {r1.status_code}")
        print(f"  Response Body: {r1.json()}")
        assert r1.status_code == 400, f"Expected 400 but got {r1.status_code}"
        assert "Invalid warehouse identifier" in r1.json()["detail"] or "does not exist" in r1.json()["detail"]
        print("  --> [PASSED] Rejected gracefully with HTTP 400 and clear explanation.")

        # Case 2: Transaction with "All"
        print("\n[Test 2] POST /api/transactions with warehouse_id = 'All':")
        r2 = await client.post("/api/transactions", json={
            "transaction_type": "RECEIPT",
            "sku": "P-1042",
            "warehouse_id": "All",
            "quantity": 100,
            "reason": "Test All insertion"
        })
        print(f"  Status Code: {r2.status_code}")
        print(f"  Response Body: {r2.json()}")
        assert r2.status_code == 400
        print("  --> [PASSED] Rejected gracefully with HTTP 400.")

        # Case 3: Transaction with non-existent warehouse "FAKE-99"
        print("\n[Test 3] POST /api/transactions with warehouse_id = 'FAKE-99':")
        r3 = await client.post("/api/transactions", json={
            "transaction_type": "SALE",
            "sku": "P-1042",
            "warehouse_id": "FAKE-99",
            "quantity": 50
        })
        print(f"  Status Code: {r3.status_code}")
        print(f"  Response Body: {r3.json()}")
        assert r3.status_code == 400
        assert "does not exist in the database" in r3.json()["detail"]
        print("  --> [PASSED] Rejected gracefully with HTTP 400.")

        # Case 4: Sales Record with "All Warehouses"
        print("\n[Test 4] POST /api/inventory/sales with warehouse_id = 'All Warehouses':")
        r4 = await client.post("/api/inventory/sales", json={
            "sku": "P-1042",
            "warehouse_id": "All Warehouses",
            "quantity": 25,
            "customer_name": "Test Hospital"
        })
        print(f"  Status Code: {r4.status_code}")
        print(f"  Response Body: {r4.json()}")
        assert r4.status_code == 400
        print("  --> [PASSED] Rejected gracefully with HTTP 400.")

        # Case 5: Valid Transaction with real warehouse "MUM-01"
        print("\n[Test 5] POST /api/transactions with valid warehouse_id = 'MUM-01':")
        r5 = await client.post("/api/transactions", json={
            "transaction_type": "RECEIPT",
            "sku": "P-1042",
            "warehouse_id": "MUM-01",
            "quantity": 50,
            "reason": "Test Valid Inbound Receipt",
            "performed_by": "QA Tester"
        })
        print(f"  Status Code: {r5.status_code}")
        print(f"  Response Body: {r5.json()}")
        assert r5.status_code == 200
        print("  --> [PASSED] Successfully committed transaction.")

    print("\n=================================================================")
    print("   ALL WAREHOUSE VALIDATION TESTS PASSED (0 DB CONSTRAINT ERRORS)")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(test_warehouse_validation())

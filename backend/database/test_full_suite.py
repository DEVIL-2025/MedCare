import asyncio
import httpx
import json
import sys
from backend.app.database import engine, Base, AsyncSessionLocal
from sqlalchemy import text

sys.stdout.reconfigure(encoding='utf-8')


async def run_comprehensive_suite():
    print("=================================================================")
    print("   MEDCARE CONTROL TOWER - COMPREHENSIVE END-TO-END SUITE")
    print("=================================================================")

    # 1. Test Direct PostgreSQL Connection & Table Counts
    async with AsyncSessionLocal() as session:
        print("\n[Step 1] PostgreSQL Table Row Verification:")
        tables = [
            "warehouses", "products", "inventory", "batches", "demand_history",
            "demand_signals", "replenishment_recommendations", "purchase_orders",
            "inventory_transfers", "alerts", "escalations", "inventory_transactions"
        ]
        for tbl in tables:
            res = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            count = res.scalar()
            print(f"  - {tbl:32} : {count} rows")

    # 2. Test FastApi Endpoints using Test Client / httpx
    print("\n[Step 2] Testing API Routers directly against FastAPI App:")
    from backend.app.main import app
    from httpx import ASGITransport

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Dashboard
        r = await client.get("/api/dashboard?warehouse=All")
        assert r.status_code == 200, f"Dashboard failed: {r.text}"
        dash_data = r.json()
        print(f"  [OK] GET /api/dashboard -> Units: {dash_data['kpis']['total_inventory_units']}, Value: {dash_data['kpis']['total_inventory_value']}, Critical SKUs: {dash_data['kpis']['critical_skus']}")

        # Inventory
        r = await client.get("/api/inventory?warehouse=All&rollup=true")
        assert r.status_code == 200, f"Inventory failed: {r.text}"
        inv_data = r.json()
        print(f"  [OK] GET /api/inventory -> {len(inv_data)} SKU items returned")

        # Demand Signals
        r = await client.get("/api/demand/signals")
        assert r.status_code == 200, f"Demand Signals failed: {r.text}"
        sig_data = r.json()
        print(f"  [OK] GET /api/demand/signals -> {len(sig_data)} active external signals returned")

        # Demand Forecast
        r = await client.get("/api/forecasts?sku=P-1042&warehouse=PAT-01")
        assert r.status_code == 200, f"Forecasts failed: {r.text}"
        fc_data = r.json()
        print(f"  [OK] GET /api/forecasts -> Baseline 30d: {fc_data['summary']['avg_daily_demand_last_30d']}, Forecast: {fc_data['summary']['forecast_demand_next_30d']}")

        # Replenishment
        r = await client.get("/api/replenishment")
        assert r.status_code == 200, f"Replenishment failed: {r.text}"
        rep_data = r.json()
        print(f"  [OK] GET /api/replenishment -> Recommendations: {len(rep_data.get('recommendations', []))}, POs: {len(rep_data.get('purchase_orders', []))}")

        # Alerts
        r = await client.get("/api/alerts?category=All Alerts")
        assert r.status_code == 200, f"Alerts failed: {r.text}"
        al_data = r.json()
        print(f"  [OK] GET /api/alerts -> Active Alerts: {len(al_data['alerts'])}, Escalations: {len(al_data['recent_activity'])}")

        # Warehouses
        r = await client.get("/api/warehouses")
        assert r.status_code == 200, f"Warehouses failed: {r.text}"
        wh_data = r.json()
        print(f"  [OK] GET /api/warehouses -> Active DCs: {len(wh_data['overview'])}, Avg Utilization: {wh_data['metrics']['average_utilization']}%")

        # Reports
        r = await client.get("/api/reports/summary?time_period=Last 14 Days")
        assert r.status_code == 200, f"Reports failed: {r.text}"
        rep_sum = r.json()
        print(f"  [OK] GET /api/reports/summary -> Total Value: {rep_sum['kpis']['total_inventory_value']}, Consumption: {rep_sum['kpis']['total_consumption']}")

        # Scenario Simulation
        r = await client.post("/api/scenarios/run", json={
            "name": "E2E Test Surge +30%",
            "demand_change_pct": 30.0,
            "lead_time_change_days": 4,
            "starting_inventory_change_pct": 0.0,
            "capacity_constraint_pct": 0.0,
            "distributor_demand_change_pct": 0.0,
            "category_filter": "All Categories",
            "warehouse_filter": "All Warehouses"
        })
        assert r.status_code == 200, f"Scenario failed: {r.text}"
        sc_data = r.json()
        print(f"  [OK] POST /api/scenarios/run -> Service Level: {sc_data['service_level']}, 16-Wk Trajectory points: {len(sc_data['impact_trend'])}")

        # Stock Transaction Execution
        r = await client.post("/api/transactions", json={
            "transaction_type": "SALE",
            "sku": "P-1042",
            "warehouse_id": "MUM-01",
            "quantity": 100,
            "reason": "E2E Automated Test Sale",
            "performed_by": "E2E Tester"
        })
        assert r.status_code == 200, f"Transaction failed: {r.text}"
        tx_data = r.json()
        print(f"  [OK] POST /api/transactions (SALE) -> {tx_data['message']}")

    print("\n=================================================================")
    print("   ALL API ROUTERS & PG SQL QUERIES CONFIRMED 100% OPERATIONAL")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_suite())

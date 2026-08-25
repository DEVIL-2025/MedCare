import asyncio
from datetime import date
from sqlalchemy import text
from backend.app.database import AsyncSessionLocal

async def seed_fefo_test_dataset():
    print("Seeding dedicated FEFO validation dataset into PostgreSQL...")
    async with AsyncSessionLocal() as s:
        # 1. Insert test warehouses if not existing
        await s.execute(text("""
            INSERT INTO warehouses (id, name, location, capacity_units, current_utilization_pct, is_active, lead_time_days)
            VALUES 
                ('WH-TEST-01', 'FEFO Test DC North', 'Test City 1', 10000, 45.0, true, 3),
                ('WH-TEST-02', 'FEFO Test DC South', 'Test City 2', 10000, 30.0, true, 3)
            ON CONFLICT (id) DO UPDATE SET is_active = true;
        """))

        # 2. Insert test product
        await s.execute(text("""
            INSERT INTO products (sku, name, category, criticality, unit, unit_cost, moq, is_active, shelf_life_days)
            VALUES 
                ('FEFO-TEST-001', 'FEFO Validation SKU 500mg', 'Test Category', 'High', 'Strips', 100.0, 100, true, 365)
            ON CONFLICT (sku) DO UPDATE SET is_active = true;
        """))

        # 3. Insert test inventory
        await s.execute(text("""
            INSERT INTO inventory (sku, warehouse_id, current_stock, reserved_stock, inbound_stock, safety_stock, reorder_point, status, risk_level)
            VALUES 
                ('FEFO-TEST-001', 'WH-TEST-01', 450, 0, 0, 100, 300, 'HEALTHY', 'low'),
                ('FEFO-TEST-001', 'WH-TEST-02', 300, 0, 0, 100, 300, 'HEALTHY', 'low')
            ON CONFLICT (sku, warehouse_id) DO UPDATE SET current_stock = EXCLUDED.current_stock;
        """))

        # 4. Clear and insert FEFO test batches
        await s.execute(text("DELETE FROM batches WHERE sku = 'FEFO-TEST-001'"))
        
        await s.execute(text("""
            INSERT INTO batches (id, sku, warehouse_id, quantity, reserved_quantity, mfg_date, expiry_date, is_quarantined, status)
            VALUES 
                ('FEFO-BATCH-A', 'FEFO-TEST-001', 'WH-TEST-01', 100, 0, '2025-09-10', '2026-09-10', false, 'ACTIVE'),
                ('FEFO-BATCH-B', 'FEFO-TEST-001', 'WH-TEST-01', 150, 0, '2025-10-15', '2026-10-15', false, 'ACTIVE'),
                ('FEFO-BATCH-C', 'FEFO-TEST-001', 'WH-TEST-01', 200, 0, '2026-01-20', '2027-01-20', false, 'ACTIVE'),
                ('FEFO-BATCH-EXP', 'FEFO-TEST-001', 'WH-TEST-01', 50, 0, '2025-01-01', '2026-07-01', false, 'EXPIRED'),
                ('FEFO-BATCH-ZERO', 'FEFO-TEST-001', 'WH-TEST-01', 0, 0, '2025-08-30', '2026-08-30', false, 'DEPLETED'),
                ('FEFO-BATCH-WH2-A', 'FEFO-TEST-001', 'WH-TEST-02', 300, 0, '2025-11-01', '2026-11-01', false, 'ACTIVE');
        """))

        await s.commit()
        print("FEFO test dataset seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_fefo_test_dataset())

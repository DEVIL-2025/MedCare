import asyncio
import sys
from backend.app.database import AsyncSessionLocal
from sqlalchemy import text
from backend.app.routers.replenishment import approve_recommendation

sys.stdout.reconfigure(encoding='utf-8')


async def test_approve():
    async with AsyncSessionLocal() as s:
        # Reset REC-A-2381-DEL-02 to PENDING
        await s.execute(text("UPDATE replenishment_recommendations SET status = 'PENDING' WHERE id = 'REC-A-2381-DEL-02'"))
        await s.commit()

        # Call approve_recommendation
        res = await approve_recommendation('REC-A-2381-DEL-02', s)
        print('APPROVE RESULT:', res)

        # Check PO
        po_res = await s.execute(text("SELECT id, sku, warehouse_id, supplier_name, quantity, status FROM purchase_orders WHERE sku = 'A-2381'"))
        for po in po_res.fetchall():
            print('CREATED PO:', po)


if __name__ == '__main__':
    asyncio.run(test_approve())

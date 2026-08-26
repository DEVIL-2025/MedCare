import pytest
from backend.app.engines.inventory_engine import InventoryEngine


def test_evaluate_inventory_status_healthy():
    status, risk = InventoryEngine.evaluate_inventory_status(
        current_stock=12000,
        reorder_point=10000,
        safety_stock=5000
    )
    assert status == "HEALTHY"
    assert risk in ["low", "medium"]


def test_evaluate_inventory_status_low_stock():
    status, risk = InventoryEngine.evaluate_inventory_status(
        current_stock=7500,
        reorder_point=10000,
        safety_stock=5000
    )
    assert status == "LOW_STOCK"
    assert risk == "high"


def test_evaluate_inventory_status_critical():
    status, risk = InventoryEngine.evaluate_inventory_status(
        current_stock=2000,
        reorder_point=10000,
        safety_stock=5000
    )
    assert status == "CRITICAL"
    assert risk == "critical"


def test_evaluate_inventory_status_out_of_stock():
    status, risk = InventoryEngine.evaluate_inventory_status(
        current_stock=0,
        reorder_point=10000,
        safety_stock=5000
    )
    assert status == "OUT_OF_STOCK"
    assert risk == "critical"


def test_evaluate_inventory_status_overstock():
    status, risk = InventoryEngine.evaluate_inventory_status(
        current_stock=25000,
        reorder_point=10000,
        safety_stock=5000
    )
    assert status == "OVERSTOCK"
    assert risk == "low"


@pytest.mark.asyncio
async def test_add_and_delete_product_cascade_db():
    from backend.app.database import AsyncSessionLocal
    from backend.app.routers.inventory import add_product, delete_product
    from backend.app.schemas.inventory import ProductCreate
    from backend.app.models.product import Product
    from backend.app.models.inventory import Inventory
    from backend.app.models.auth import User
    from sqlalchemy import select

    admin_user = User(id="USR-ADMIN-TEST", role_id="ADMIN", is_active=True)

    async with AsyncSessionLocal() as session:
        # Create test product
        create_payload = ProductCreate(
            sku="TEST-PROD-999",
            name="Test Medicine 999",
            category="Analgesics",
            criticality="Medium",
            unit="Strips",
            shelf_life_days=730,
            default_reorder_point=150,
            default_safety_stock=50,
            moq=50,
            unit_cost=30.0,
            initial_stock=100,
            initial_warehouse_id="MUM-01"
        )
        res_add = await add_product(payload=create_payload, current_user=admin_user, db=session)
        assert res_add["success"] is True

        # Verify product exists in database
        check_res = await session.execute(select(Product).where(Product.sku == "TEST-PROD-999"))
        assert check_res.scalars().first() is not None

        # Verify inventory was created
        inv_check = await session.execute(select(Inventory).where(Inventory.sku == "TEST-PROD-999"))
        assert len(inv_check.scalars().all()) > 0

        # Delete product
        res_del = await delete_product(sku="TEST-PROD-999", current_user=admin_user, db=session)
        assert res_del["success"] is True

        # Verify product is completely gone from products table in database
        final_check = await session.execute(select(Product).where(Product.sku == "TEST-PROD-999"))
        assert final_check.scalars().first() is None

        # Verify inventory records are completely gone
        final_inv = await session.execute(select(Inventory).where(Inventory.sku == "TEST-PROD-999"))
        assert len(final_inv.scalars().all()) == 0


@pytest.mark.asyncio
async def test_manager_forbidden_to_create_product():
    from fastapi import HTTPException
    from backend.app.dependencies.auth import require_permission
    from backend.app.models.auth import User

    manager_user = User(id="USR-MANAGER-TEST", role_id="MANAGER", is_active=True)
    setattr(manager_user, "permission_codes", {"inventory.view", "inventory.record_stock_transaction"})

    checker = require_permission("inventory.create_product")

    # Manager role lacks inventory.create_product -> must raise 403 HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=manager_user)

    assert exc_info.value.status_code == 403
    assert "inventory.create_product" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_and_get_warehouse():
    from backend.app.database import AsyncSessionLocal
    from backend.app.routers.warehouses import add_warehouse, delete_warehouse, get_warehouses_overview
    from backend.app.schemas.warehouse import WarehouseCreate
    from backend.app.models.warehouse import Warehouse
    from sqlalchemy import select, delete as sql_delete

    async with AsyncSessionLocal() as session:
        # Clean any leftover test warehouse
        await session.execute(sql_delete(Warehouse).where(Warehouse.id == "TEST-WH-01"))
        await session.commit()

        wh_payload = WarehouseCreate(
            id="TEST-WH-01",
            name="Test Distribution Center",
            location="Ahmedabad, Gujarat",
            tier="Tier-2 DC",
            region="West",
            capacity_units=12000,
            current_utilization_pct=15.0,
            health_score=95,
            status="Healthy",
            map_x=42.0,
            map_y=58.0
        )
        res = await add_warehouse(payload=wh_payload, db=session)
        assert res["success"] is True
        assert res["warehouse"]["id"] == "TEST-WH-01"

        # Verify in overview
        overview_data = await get_warehouses_overview(db=session)
        matching = [w for w in overview_data["overview"] if w["id"] == "TEST-WH-01"]
        assert len(matching) == 1
        assert matching[0]["name"] == "Test Distribution Center"

        # Clean up
        await session.execute(sql_delete(Warehouse).where(Warehouse.id == "TEST-WH-01"))
        await session.commit()


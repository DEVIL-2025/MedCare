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


@pytest.mark.asyncio
async def test_update_inventory_config_warehouse_specific():
    from backend.app.database import AsyncSessionLocal
    from backend.app.routers.inventory import add_product, update_inventory_config, delete_product
    from backend.app.schemas.inventory import ProductCreate, InventoryConfigUpdate
    from backend.app.models.inventory import Inventory
    from backend.app.models.product import Product
    from backend.app.models.auth import User
    from sqlalchemy import select

    admin_user = User(id="USR-ADMIN-TEST", role_id="ADMIN", is_active=True)

    async with AsyncSessionLocal() as session:
        # Create test product
        create_payload = ProductCreate(
            sku="TEST-CONFIG-001",
            name="Config Test Drug",
            category="Antibiotics",
            criticality="High",
            unit="Vials",
            shelf_life_days=730,
            default_reorder_point=200,
            default_safety_stock=80,
            moq=50,
            unit_cost=100.0,
            initial_stock=300,
            initial_warehouse_id="MUM-01"
        )
        await add_product(payload=create_payload, current_user=admin_user, db=session)

        # Update MUM-01 specific inventory settings
        update_mum = InventoryConfigUpdate(
            reorder_point=450,
            safety_stock=180,
            unit_cost=125.50,
            moq=100
        )
        res_mum = await update_inventory_config(
            warehouse_id="MUM-01",
            sku="TEST-CONFIG-001",
            payload=update_mum,
            current_user=admin_user,
            db=session
        )
        assert res_mum["success"] is True
        assert res_mum["reorderPoint"] == 450
        assert res_mum["safetyStock"] == 180
        assert res_mum["unitCost"] == 125.50

        # Verify MUM-01 in DB
        inv_mum = (await session.execute(
            select(Inventory).where(Inventory.sku == "TEST-CONFIG-001", Inventory.warehouse_id == "MUM-01")
        )).scalars().first()
        assert inv_mum.reorder_point == 450
        assert inv_mum.safety_stock == 180

        # Verify DEL-02 in DB is isolated and retains default ROP
        inv_del = (await session.execute(
            select(Inventory).where(Inventory.sku == "TEST-CONFIG-001", Inventory.warehouse_id == "DEL-02")
        )).scalars().first()
        assert inv_del.reorder_point == 200
        assert inv_del.safety_stock == 80

        # Clean up
        await delete_product(sku="TEST-CONFIG-001", current_user=admin_user, db=session)


@pytest.mark.asyncio
async def test_delete_warehouse_inventory_preserves_product():
    from backend.app.database import AsyncSessionLocal
    from backend.app.routers.inventory import add_product, delete_warehouse_inventory, delete_product
    from backend.app.schemas.inventory import ProductCreate
    from backend.app.models.inventory import Inventory
    from backend.app.models.product import Product
    from backend.app.models.auth import User
    from sqlalchemy import select

    admin_user = User(id="USR-ADMIN-TEST", role_id="ADMIN", is_active=True)

    async with AsyncSessionLocal() as session:
        # Create test product
        create_payload = ProductCreate(
            sku="TEST-DEL-WH-002",
            name="Warehouse Deletion Test Drug",
            category="Analgesics",
            criticality="Medium",
            unit="Strips",
            shelf_life_days=730,
            default_reorder_point=100,
            default_safety_stock=40,
            moq=50,
            unit_cost=45.0,
            initial_stock=150,
            initial_warehouse_id="MUM-01"
        )
        await add_product(payload=create_payload, current_user=admin_user, db=session)

        # Delete MUM-01 warehouse inventory record
        del_res = await delete_warehouse_inventory(
            warehouse_id="MUM-01",
            sku="TEST-DEL-WH-002",
            current_user=admin_user,
            db=session
        )
        assert del_res["success"] is True

        # Verify MUM-01 record is gone
        inv_mum = (await session.execute(
            select(Inventory).where(Inventory.sku == "TEST-DEL-WH-002", Inventory.warehouse_id == "MUM-01")
        )).scalars().first()
        assert inv_mum is None

        # Verify DEL-02 record STILL exists
        inv_del = (await session.execute(
            select(Inventory).where(Inventory.sku == "TEST-DEL-WH-002", Inventory.warehouse_id == "DEL-02")
        )).scalars().first()
        assert inv_del is not None

        # Verify Product master record STILL exists
        prod = (await session.execute(
            select(Product).where(Product.sku == "TEST-DEL-WH-002")
        )).scalars().first()
        assert prod is not None

        # Clean up
        await delete_product(sku="TEST-DEL-WH-002", current_user=admin_user, db=session)


@pytest.mark.asyncio
async def test_safety_stock_sellable_not_locked():
    from backend.app.database import AsyncSessionLocal
    from backend.app.routers.inventory import add_product, delete_product
    from backend.app.schemas.inventory import ProductCreate
    from backend.app.engines.inventory_engine import InventoryEngine
    from backend.app.models.inventory import Inventory
    from backend.app.models.auth import User
    from sqlalchemy import select

    admin_user = User(id="USR-ADMIN-TEST", role_id="ADMIN", is_active=True)

    async with AsyncSessionLocal() as session:
        # Create product with 100 stock and 60 safety stock
        create_payload = ProductCreate(
            sku="TEST-SELL-SS-003",
            name="Safety Stock Sellable Drug",
            category="Vitamins",
            criticality="Medium",
            unit="Bottles",
            shelf_life_days=730,
            default_reorder_point=80,
            default_safety_stock=60,
            moq=50,
            unit_cost=55.0,
            initial_stock=100,
            initial_warehouse_id="MUM-01"
        )
        await add_product(payload=create_payload, current_user=admin_user, db=session)

        # Sell 70 units (reducing stock from 100 to 30, which is BELOW safety stock of 60)
        # This MUST succeed because Safety Stock is a buffer target, NOT permanently locked stock
        tx, inv = await InventoryEngine.process_transaction(
            session=session,
            transaction_type="SALE",
            sku="TEST-SELL-SS-003",
            warehouse_id="MUM-01",
            quantity=70,
            reference_id="TEST-SO-001",
            performed_by="Sales Dispatch"
        )
        await session.commit()

        assert inv.current_stock == 30
        assert inv.status == "CRITICAL"  # Because current_stock (30) < safety_stock (60)
        assert inv.risk_level == "critical"

        # Clean up
        await delete_product(sku="TEST-SELL-SS-003", current_user=admin_user, db=session)



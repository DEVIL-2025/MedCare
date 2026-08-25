import asyncio
from datetime import datetime, date, timedelta, timezone
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.app.database import AsyncSessionLocal, engine, Base, init_database
from backend.app.models import (
    Product, Warehouse, Inventory, Batch, InventoryTransaction,
    DemandHistory, DistributorOrder, SeasonalEvent, Promotion,
    ForecastRecord, DemandSurgeEvent, InventoryRisk,
    ReplenishmentRecommendation, PurchaseOrder, InventoryTransfer,
    Alert, NotificationLog, Scenario, ScenarioResult, SystemSetting,
    DemandSignal, AlertEscalation, SalesOrder,
    User, Role, Permission, RolePermission, AuditLog
)
from backend.app.services.auth_service import AuthService

PERMISSIONS_DATA = [
    # Dashboard
    {"id": "dashboard.view", "permission_code": "dashboard.view", "module": "dashboard", "action": "view", "description": "View executive control tower dashboard and KPIs"},
    {"id": "dashboard.refresh", "permission_code": "dashboard.refresh", "module": "dashboard", "action": "refresh", "description": "Trigger dynamic metrics recalculation"},
    {"id": "dashboard.execute_recommendation", "permission_code": "dashboard.execute_recommendation", "module": "dashboard", "action": "execute", "description": "Execute 1-click executive recommendations"},

    # Inventory
    {"id": "inventory.view", "permission_code": "inventory.view", "module": "inventory", "action": "view", "description": "View DC stock balances and product batches"},
    {"id": "inventory.create_product", "permission_code": "inventory.create_product", "module": "inventory", "action": "create", "description": "Register new pharmaceutical product in catalog"},
    {"id": "inventory.record_sale", "permission_code": "inventory.record_sale", "module": "inventory", "action": "create", "description": "Record hospital or distributor sale and FEFO decrement"},
    {"id": "inventory.record_stock_transaction", "permission_code": "inventory.record_stock_transaction", "module": "inventory", "action": "create", "description": "Execute receipt, adjustment, or consumption stock transaction"},
    {"id": "inventory.create_transfer", "permission_code": "inventory.create_transfer", "module": "inventory", "action": "create", "description": "Initiate inter-DC stock rebalancing transfer"},
    {"id": "inventory.view_transactions", "permission_code": "inventory.view_transactions", "module": "inventory", "action": "view", "description": "View historical audit trail of inventory transactions"},
    {"id": "inventory.export", "permission_code": "inventory.export", "module": "inventory", "action": "export", "description": "Export inventory data to CSV"},
    {"id": "inventory.delete_product", "permission_code": "inventory.delete_product", "module": "inventory", "action": "delete", "description": "Permanently delete product catalog entry and cascade dependent records"},

    # Demand Forecast
    {"id": "forecast.view", "permission_code": "forecast.view", "module": "forecast", "action": "view", "description": "View ML demand curves and sensed velocity forecasts"},
    {"id": "forecast.view_history", "permission_code": "forecast.view_history", "module": "forecast", "action": "view", "description": "View historical consumption time-series"},
    {"id": "forecast.view_accuracy", "permission_code": "forecast.view_accuracy", "module": "forecast", "action": "view", "description": "View ML model transparency, accuracy, and lineage"},
    {"id": "forecast.run", "permission_code": "forecast.run", "module": "forecast", "action": "run", "description": "Execute automated demand sensing and surge detection pipeline"},
    {"id": "forecast.train", "permission_code": "forecast.train", "module": "forecast", "action": "train", "description": "Trigger compute-heavy ML forecaster retraining"},

    # Replenishment
    {"id": "replenishment.view", "permission_code": "replenishment.view", "module": "replenishment", "action": "view", "description": "View replenishment recommendations and purchase orders"},
    {"id": "replenishment.approve", "permission_code": "replenishment.approve", "module": "replenishment", "action": "approve", "description": "Approve purchase order and replenishment recommendation"},
    {"id": "replenishment.reject", "permission_code": "replenishment.reject", "module": "replenishment", "action": "reject", "description": "Reject replenishment recommendation"},
    {"id": "replenishment.create_transfer", "permission_code": "replenishment.create_transfer", "module": "replenishment", "action": "create", "description": "Approve and execute inter-DC transfer opportunity"},
    {"id": "replenishment.view_fefo", "permission_code": "replenishment.view_fefo", "module": "replenishment", "action": "view", "description": "View live FEFO batch allocations"},
    {"id": "replenishment.view_purchase_orders", "permission_code": "replenishment.view_purchase_orders", "module": "replenishment", "action": "view", "description": "View historical and approved supplier purchase orders"},

    # Alerts
    {"id": "alerts.view", "permission_code": "alerts.view", "module": "alerts", "action": "view", "description": "View inventory risk alerts and root-cause diagnoses"},
    {"id": "alerts.acknowledge", "permission_code": "alerts.acknowledge", "module": "alerts", "action": "acknowledge", "description": "Acknowledge active alert and take ownership"},
    {"id": "alerts.resolve", "permission_code": "alerts.resolve", "module": "alerts", "action": "resolve", "description": "Mark alert resolved post-action"},

    # Warehouses
    {"id": "warehouses.view", "permission_code": "warehouses.view", "module": "warehouses", "action": "view", "description": "View DC locations, utilization, and capacity metrics"},
    {"id": "warehouses.view_utilization", "permission_code": "warehouses.view_utilization", "module": "warehouses", "action": "view", "description": "View historical capacity utilization metrics"},
    {"id": "warehouses.view_trends", "permission_code": "warehouses.view_trends", "module": "warehouses", "action": "view", "description": "View warehouse volume and storage trends"},
    {"id": "warehouses.manage", "permission_code": "warehouses.manage", "module": "warehouses", "action": "manage", "description": "Register, configure, edit, and decommission warehouse distribution centers"},

    # Reports
    {"id": "reports.view", "permission_code": "reports.view", "module": "reports", "action": "view", "description": "View operational and executive SCM report analytics"},
    {"id": "reports.generate", "permission_code": "reports.generate", "module": "reports", "action": "generate", "description": "Filter and generate multi-dimensional reports"},
    {"id": "reports.export", "permission_code": "reports.export", "module": "reports", "action": "export", "description": "Export analytical report tables to CSV"},

    # User Management
    {"id": "users.view", "permission_code": "users.view", "module": "users", "action": "view", "description": "View user accounts and role assignments"},
    {"id": "users.create", "permission_code": "users.create", "module": "users", "action": "create", "description": "Create new system user accounts"},
    {"id": "users.edit", "permission_code": "users.edit", "module": "users", "action": "edit", "description": "Edit user profiles and credentials"},
    {"id": "users.deactivate", "permission_code": "users.deactivate", "module": "users", "action": "deactivate", "description": "Activate or deactivate user accounts"},
    {"id": "users.reset_password", "permission_code": "users.reset_password", "module": "users", "action": "reset_password", "description": "Reset user passwords"},
    {"id": "users.assign_role", "permission_code": "users.assign_role", "module": "users", "action": "assign_role", "description": "Assign or update user roles"},

    # Audit
    {"id": "audit.view", "permission_code": "audit.view", "module": "audit", "action": "view", "description": "View immutable system audit logs"},

    # System
    {"id": "system.configuration", "permission_code": "system.configuration", "module": "system", "action": "configure", "description": "Modify algorithmic and system configuration parameters"},
    {"id": "system.database", "permission_code": "system.database", "module": "system", "action": "database", "description": "Access system database diagnostics"},
    {"id": "system.migrations", "permission_code": "system.migrations", "module": "system", "action": "migrations", "description": "Run and inspect database schema migrations"},
    {"id": "system.data_management", "permission_code": "system.data_management", "module": "system", "action": "data_management", "description": "Administrative data management operations"}
]


async def seed_auth_data(session: AsyncSession, force: bool = False):
    """Seeds roles, permissions, role-permission mappings, and initial users into PostgreSQL."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Seed Roles
    roles_res = await session.execute(select(Role))
    existing_roles = {r.id: r for r in roles_res.scalars().all()}

    if not existing_roles or force:
        admin_role = existing_roles.get("ADMIN") or Role(
            id="ADMIN",
            name="ADMIN",
            description="Full administrative, security, and operational access across the entire platform.",
            created_at=now_utc
        )
        manager_role = existing_roles.get("MANAGER") or Role(
            id="MANAGER",
            name="MANAGER",
            description="Operational supply chain access across inventory, replenishment, demand, alerts, and reports.",
            created_at=now_utc
        )
        if "ADMIN" not in existing_roles:
            session.add(admin_role)
        if "MANAGER" not in existing_roles:
            session.add(manager_role)
        await session.flush()

    # 2. Seed Permissions
    perms_res = await session.execute(select(Permission))
    existing_perms = {p.id: p for p in perms_res.scalars().all()}

    new_perms = []
    for p_data in PERMISSIONS_DATA:
        if p_data["id"] not in existing_perms:
            perm = Permission(**p_data)
            session.add(perm)
            new_perms.append(perm)
    if new_perms:
        await session.flush()

    # 3. Seed Role-Permissions Mapping
    role_perms_res = await session.execute(select(RolePermission))
    existing_rp = {(rp.role_id, rp.permission_id) for rp in role_perms_res.scalars().all()}

    admin_restricted_perms = set()  # Admin gets everything
    manager_restricted_perms = {
        "inventory.delete_product",
        "forecast.train",
        "warehouses.manage",
        "users.view",
        "users.create",
        "users.edit",
        "users.deactivate",
        "users.reset_password",
        "users.assign_role",
        "audit.view",
        "system.configuration",
        "system.database",
        "system.migrations",
        "system.data_management"
    }

    new_mappings = []
    for p_data in PERMISSIONS_DATA:
        p_id = p_data["id"]
        # Admin mapping
        if ("ADMIN", p_id) not in existing_rp:
            new_mappings.append(RolePermission(role_id="ADMIN", permission_id=p_id))
        # Manager mapping (if not restricted)
        if p_id not in manager_restricted_perms and ("MANAGER", p_id) not in existing_rp:
            new_mappings.append(RolePermission(role_id="MANAGER", permission_id=p_id))

    if new_mappings:
        session.add_all(new_mappings)
        await session.flush()

    # 4. Seed Initial Users
    users_res = await session.execute(select(User))
    existing_users = {u.user_id: u for u in users_res.scalars().all()}

    initial_users = [
        {
            "id": "USR-ADMIN-01",
            "user_id": "admin",
            "email": "admin@medcarepharma.com",
            "full_name": "System Administrator",
            "password_hash": AuthService.hash_password("Admin@12345"),
            "role_id": "ADMIN",
            "is_active": True,
            "must_change_password": False,
            "created_at": now_utc,
            "updated_at": now_utc,
            "created_by": "System"
        },
        {
            "id": "USR-MGR-01",
            "user_id": "manager",
            "email": "manager@medcarepharma.com",
            "full_name": "Rohan Mehta",
            "password_hash": AuthService.hash_password("Manager@12345"),
            "role_id": "MANAGER",
            "is_active": True,
            "must_change_password": False,
            "created_at": now_utc,
            "updated_at": now_utc,
            "created_by": "System"
        },
        {
            "id": "USR-MGR-02",
            "user_id": "aditi.rao",
            "email": "aditi.rao@medcarepharma.com",
            "full_name": "Dr. Aditi Rao",
            "password_hash": AuthService.hash_password("Manager@12345"),
            "role_id": "MANAGER",
            "is_active": True,
            "must_change_password": False,
            "created_at": now_utc,
            "updated_at": now_utc,
            "created_by": "System"
        }
    ]

    for u_data in initial_users:
        if u_data["user_id"] not in existing_users:
            session.add(User(**u_data))
        else:
            u_obj = existing_users[u_data["user_id"]]
            u_obj.is_active = True
            u_obj.password_hash = u_data["password_hash"]
            u_obj.must_change_password = False

    await session.commit()
    print("[Seeder] Auth & RBAC roles, permissions, and users successfully synchronized in PostgreSQL!")


async def seed_database(session: AsyncSession, force: bool = False):
    """Seed synthetic realistic data for MedCare Pharma SCM Control Tower with small values."""
    print("[Seeder] Initializing Auth & RBAC tables...")
    await seed_auth_data(session, force=force)

    print("[Seeder] Checking existing business data...")
    if not force:
        existing = await session.execute(select(Product))
        if existing.scalars().first():
            print("[Seeder] Database already populated. Re-verifying structure...")
            return

    if force:
        print("[Seeder] Force reseed requested. Clearing existing tables...")
        for model in [
            NotificationLog, AlertEscalation, Alert, InventoryTransfer, PurchaseOrder,
            ReplenishmentRecommendation, ScenarioResult, Scenario,
            InventoryRisk, DemandSurgeEvent, ForecastRecord,
            DemandSignal, Promotion, SeasonalEvent, DistributorOrder, DemandHistory,
            SalesOrder, InventoryTransaction, Batch, Inventory, Warehouse, Product, SystemSetting
        ]:
            await session.execute(delete(model))
        await session.commit()

    print("[Seeder] Seeding Products...")
    products = [Product(**p) for p in PRODUCTS_DATA]
    session.add_all(products)
    await session.flush()

    print("[Seeder] Seeding Warehouses...")
    warehouses = [Warehouse(**w) for w in WAREHOUSES_DATA]
    session.add_all(warehouses)
    await session.flush()

    print("[Seeder] Seeding Inventory & Batches with Small Values...")
    today = date(2026, 8, 24)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Specific Scenario Setup:
    # 1. P-1042 (Paracetamol 500mg)
    #    - MUM-01: Excess near-expiry (450 units expiring in 45 days)
    #    - PAT-01: Severe shortage (25 units stock vs surge demand)
    #    - BLR-01: Low stock (180 units vs ROP 250)
    # 2. C-5562 (Cough Syrup)
    #    - MUM-01: Near-expiry batch (140 units, expires in 22 days)
    # 3. AZ-3391 (Azithromycin):
    #    - HYD-01: Out of stock (0 units)
    # 4. I-7783 (Ibuprofen):
    #    - HYD-01: Low stock (190 units)
    
    batches_to_add = []
    inventory_to_add = []
    transactions_to_add = []
    
    for prod in PRODUCTS_DATA:
        sku = prod["sku"]
        for wh in WAREHOUSES_DATA:
            wh_id = wh["id"]
            
            # Default stock heuristics with small values
            if sku == "P-1042" and wh_id == "MUM-01":
                curr_stock = 550
                res_stock = 40
                inbound = 0
                status = "OVERSTOCK"
                risk_level = "low"
                doc = 42.0
                # Batch expiring in 45 days
                b1 = Batch(id=f"BAT-{sku}-MUM-01", sku=sku, warehouse_id=wh_id, quantity=450, reserved_quantity=0, mfg_date=today - timedelta(days=680), expiry_date=today + timedelta(days=45), status="NEAR_EXPIRY")
                b2 = Batch(id=f"BAT-{sku}-MUM-02", sku=sku, warehouse_id=wh_id, quantity=100, reserved_quantity=0, mfg_date=today - timedelta(days=100), expiry_date=today + timedelta(days=630), status="ACTIVE")
                batches_to_add.extend([b1, b2])

            elif sku == "P-1042" and wh_id == "PAT-01":
                curr_stock = 25
                res_stock = 5
                inbound = 0
                status = "CRITICAL"
                risk_level = "critical"
                doc = 3.2  # Stockout in ~3.2 days!
                b1 = Batch(id=f"BAT-{sku}-PAT-01", sku=sku, warehouse_id=wh_id, quantity=25, reserved_quantity=0, mfg_date=today - timedelta(days=90), expiry_date=today + timedelta(days=640), status="ACTIVE")
                batches_to_add.append(b1)

            elif sku == "P-1042" and wh_id == "BLR-01":
                curr_stock = 180
                res_stock = 15
                inbound = 0
                status = "LOW_STOCK"
                risk_level = "high"
                doc = 9.5
                b1 = Batch(id=f"BAT-{sku}-BLR-01", sku=sku, warehouse_id=wh_id, quantity=180, reserved_quantity=0, mfg_date=today - timedelta(days=120), expiry_date=today + timedelta(days=610), status="ACTIVE")
                batches_to_add.append(b1)

            elif sku == "C-5562" and wh_id == "MUM-01":
                curr_stock = 140
                res_stock = 10
                inbound = 0
                status = "LOW_STOCK"
                risk_level = "high"
                doc = 14.0
                # Expiring in 22 days
                b1 = Batch(id=f"BAT-{sku}-MUM-01", sku=sku, warehouse_id=wh_id, quantity=140, reserved_quantity=0, mfg_date=today - timedelta(days=708), expiry_date=today + timedelta(days=22), status="CRITICAL")
                batches_to_add.append(b1)

            elif sku == "AZ-3391" and wh_id == "HYD-01":
                curr_stock = 0
                res_stock = 0
                inbound = 50
                status = "OUT_OF_STOCK"
                risk_level = "critical"
                doc = 0.0

            elif sku == "I-7783" and wh_id == "HYD-01":
                curr_stock = 190
                res_stock = 20
                inbound = 0
                status = "LOW_STOCK"
                risk_level = "critical"
                doc = 8.5
                b1 = Batch(id=f"BAT-{sku}-HYD-01", sku=sku, warehouse_id=wh_id, quantity=190, reserved_quantity=0, mfg_date=today - timedelta(days=150), expiry_date=today + timedelta(days=580), status="ACTIVE")
                batches_to_add.append(b1)

            elif sku == "M-5521" and wh_id == "CHE-01":
                curr_stock = 650
                res_stock = 40
                inbound = 0
                status = "HEALTHY"
                risk_level = "low"
                doc = 45.0
                b1 = Batch(id=f"BAT-{sku}-CHE-01", sku=sku, warehouse_id=wh_id, quantity=650, reserved_quantity=0, mfg_date=today - timedelta(days=90), expiry_date=today + timedelta(days=640), status="ACTIVE")
                batches_to_add.append(b1)

            else:
                # Standard distributed profile with small realistic numbers
                factor = 1.2 if wh["tier"] == "Metro DC" else (0.8 if wh["tier"] == "Tier-1 DC" else 0.4)
                curr_stock = max(10, int(prod["default_reorder_point"] * factor * random.uniform(0.7, 1.4)))
                res_stock = max(0, int(curr_stock * random.uniform(0.05, 0.12)))
                inbound = int(prod["moq"]) if random.random() < 0.3 else 0
                
                if curr_stock == 0:
                    status, risk_level, doc = "OUT_OF_STOCK", "critical", 0.0
                elif curr_stock < prod["default_safety_stock"]:
                    status, risk_level, doc = "CRITICAL", "critical", round(curr_stock / max(1.0, (prod["default_reorder_point"] / 15)), 1)
                elif curr_stock < prod["default_reorder_point"]:
                    status, risk_level, doc = "LOW_STOCK", "high", round(curr_stock / max(1.0, (prod["default_reorder_point"] / 15)), 1)
                elif curr_stock > prod["default_reorder_point"] * 2.2:
                    status, risk_level, doc = "OVERSTOCK", "low", round(curr_stock / max(1.0, (prod["default_reorder_point"] / 15)), 1)
                else:
                    status, risk_level, doc = "HEALTHY", "low", round(curr_stock / max(1.0, (prod["default_reorder_point"] / 15)), 1)
                
                # Create standard active batch
                exp_days = random.choice([400, 520, 650, 700])
                b1 = Batch(
                    id=f"BAT-{sku}-{wh_id}-{random.randint(100, 999)}",
                    sku=sku,
                    warehouse_id=wh_id,
                    quantity=curr_stock,
                    reserved_quantity=res_stock,
                    mfg_date=today - timedelta(days=random.randint(30, 180)),
                    expiry_date=today + timedelta(days=exp_days),
                    status="ACTIVE"
                )
                batches_to_add.append(b1)

            inv = Inventory(
                sku=sku,
                warehouse_id=wh_id,
                current_stock=curr_stock,
                reserved_stock=res_stock,
                inbound_stock=inbound,
                reorder_point=prod["default_reorder_point"],
                safety_stock=prod["default_safety_stock"],
                status=status,
                risk_level=risk_level,
                days_of_cover=doc,
                last_recalculated_at=now_utc
            )
            inventory_to_add.append(inv)
            
            # Initial baseline transaction
            tx = InventoryTransaction(
                transaction_type="RECEIPT",
                sku=sku,
                warehouse_id=wh_id,
                quantity=curr_stock,
                previous_stock=0,
                new_stock=curr_stock,
                reference_id=f"INIT-{wh_id}-{sku}",
                reason="Initial inventory load",
                performed_by="System Seeder",
                timestamp=now_utc - timedelta(days=10)
            )
            transactions_to_add.append(tx)

    session.add_all(batches_to_add)
    session.add_all(inventory_to_add)
    session.add_all(transactions_to_add)
    await session.flush()

    print("[Seeder] Seeding 90 Days Historical Demand & Seasonal Events...")
    # Seasonal Event: Flu Season
    flu_event = SeasonalEvent(
        name="Annual Flu Season Spike",
        event_type="Seasonal",
        start_date=today + timedelta(days=7),
        end_date=today + timedelta(days=90),
        impact_level="High",
        expected_uplift_pct=60.0,
        impacted_categories="Analgesics,Cough & Cold,Respiratory,Antibiotics",
        impacted_region="All"
    )
    monsoon_event = SeasonalEvent(
        name="Monsoon Vector Wave",
        event_type="Seasonal",
        start_date=today - timedelta(days=45),
        end_date=today + timedelta(days=15),
        impact_level="Medium",
        expected_uplift_pct=25.0,
        impacted_categories="Analgesics,Antibiotics,Gastro Care",
        impacted_region="South,West"
    )
    festive_promo = Promotion(
        name="Festive Health Pack Promotion",
        sku="V-1122",
        start_date=today + timedelta(days=12),
        end_date=today + timedelta(days=22),
        expected_uplift_pct=25.0,
        discount_pct=15.0
    )
    session.add_all([flu_event, monsoon_event, festive_promo])
    await session.flush()

    demand_records = []
    for day_offset in range(90, 0, -1):
        record_date = today - timedelta(days=day_offset)
        dow = record_date.weekday()
        # Day of week multiplier: higher Mon-Fri
        dow_factor = 1.15 if dow in [0, 1, 2, 3, 4] else 0.80

        for prod in PRODUCTS_DATA:
            sku = prod["sku"]
            base_rate = max(3.0, prod["default_reorder_point"] / 20.0)
            
            for wh in WAREHOUSES_DATA:
                wh_id = wh["id"]
                wh_factor = 1.3 if wh["tier"] == "Metro DC" else (0.9 if wh["tier"] == "Tier-1 DC" else 0.5)
                # Apply recent surge for Flu Season items in Tier-2/Tier-1 DCs
                surge = 1.45 if (prod["category"] in ["Analgesics", "Cough & Cold"] and day_offset <= 14 and wh_id in ["PAT-01", "DEL-02", "HYD-01"]) else 1.0
                
                daily_demand = max(1, int(base_rate * wh_factor * dow_factor * surge * random.uniform(0.85, 1.15)))
                dh = DemandHistory(
                    sku=sku,
                    warehouse_id=wh_id,
                    date=record_date,
                    actual_sales=daily_demand,
                    unfulfilled_demand=max(1, int(daily_demand * 0.2)) if (sku == "P-1042" and wh_id == "PAT-01" and day_offset <= 5) else 0,
                    channel="Distributor",
                    region=wh["region"]
                )
                demand_records.append(dh)

    session.add_all(demand_records)
    await session.flush()

    print("[Seeder] Seeding Distributor Orders with Small Values...")
    distributor_orders = [
        DistributorOrder(
            id="DO-2026-9901",
            distributor_name="Apollo Pharmacy Network",
            sku="P-1042",
            warehouse_id="PAT-01",
            region="East",
            order_quantity=120,
            order_date=today - timedelta(days=1),
            required_date=today + timedelta(days=3),
            priority="Critical",
            status="PENDING"
        ),
        DistributorOrder(
            id="DO-2026-9902",
            distributor_name="MedPlus Health Services",
            sku="C-5562",
            warehouse_id="DEL-02",
            region="North",
            order_quantity=90,
            order_date=today - timedelta(days=2),
            required_date=today + timedelta(days=4),
            priority="Urgent",
            status="PENDING"
        ),
        DistributorOrder(
            id="DO-2026-9903",
            distributor_name="Fortis Healthcare Central",
            sku="AZ-3391",
            warehouse_id="DEL-02",
            region="North",
            order_quantity=60,
            order_date=today - timedelta(days=1),
            required_date=today + timedelta(days=2),
            priority="Critical",
            status="PENDING"
        ),
        DistributorOrder(
            id="DO-2026-9904",
            distributor_name="Wellness Forever Retail",
            sku="IN-6620",
            warehouse_id="MUM-01",
            region="West",
            order_quantity=30,
            order_date=today - timedelta(days=1),
            required_date=today + timedelta(days=5),
            priority="Normal",
            status="PENDING"
        )
    ]
    session.add_all(distributor_orders)
    await session.flush()

    print("[Seeder] Seeding Initial Recommendations, Transfers, Alerts & Notifications...")
    
    # 1. Primary Recommendation: Flu Season Stockout on PAT-01 -> Transfer from MUM-01 near-expiry!
    rec1 = ReplenishmentRecommendation(
        id="REC-20260824-001",
        sku="P-1042",
        warehouse_id="PAT-01",
        current_stock=25,
        forecast_demand_30d=320.0,
        safety_stock=100,
        recommended_quantity=120,
        recommended_frequency="Every 7 days (Surge Cadence)",
        next_review_date=today + timedelta(days=7),
        decision_type="TRANSFER",
        preferred_source="MUM-01",
        estimated_cost_inr=3000.0,
        priority="critical",
        reason_what="Transfer 120 units of Paracetamol 500mg from MUM-01 to PAT-01",
        reason_why="PAT-01 has 3.2 days cover with +60% flu season surge. MUM-01 has 450 excess units expiring in 45 days.",
        reason_when="Transfer immediately (dispatch today, arrival in 3 days).",
        reason_impact="Eliminates immediate stockout risk in Tier-2 East DC and prevents ₹11.2K expiry write-off in MUM-01.",
        status="PENDING",
        requested_by="P1 Demand Sensing Engine"
    )

    rec2 = ReplenishmentRecommendation(
        id="REC-20260824-002",
        sku="P-1042",
        warehouse_id="BLR-01",
        current_stock=180,
        forecast_demand_30d=260.0,
        safety_stock=100,
        recommended_quantity=150,
        recommended_frequency="Every 14 days",
        next_review_date=today + timedelta(days=14),
        decision_type="REPLENISH",
        preferred_source="SUPPLIER",
        estimated_cost_inr=3750.0,
        priority="critical",
        reason_what="Procure 150 units from HealthGen Pharma",
        reason_why="Stock is below reorder point (180 < 250) and forecast is trending upward.",
        reason_when="Order within 24 hours.",
        reason_impact="Restores safety stock cover to 22 days.",
        status="PENDING",
        requested_by="E1 Restock Engine"
    )

    rec3 = ReplenishmentRecommendation(
        id="REC-20260824-003",
        sku="I-7783",
        warehouse_id="HYD-01",
        current_stock=190,
        forecast_demand_30d=240.0,
        safety_stock=80,
        recommended_quantity=100,
        recommended_frequency="Every 14 days",
        next_review_date=today + timedelta(days=14),
        decision_type="REPLENISH",
        preferred_source="SUPPLIER",
        estimated_cost_inr=4500.0,
        priority="critical",
        reason_what="Procure 100 units of Ibuprofen 400mg",
        reason_why="Projected stockout in 8 days with lead time of 4 days.",
        reason_when="Issue PO within 24 hours.",
        reason_impact="Prevents stockout in Hyderabad region.",
        status="PENDING",
        requested_by="E1 Restock Engine"
    )
    session.add_all([rec1, rec2, rec3])
    await session.flush()

    # Pre-calculated Transfer Candidate
    trf1 = InventoryTransfer(
        id="TRF-20260824-001",
        sku="P-1042",
        source_warehouse_id="MUM-01",
        destination_warehouse_id="PAT-01",
        batch_id="BAT-P-1042-MUM-01",
        quantity=120,
        available_at_source=450,
        transfer_lead_time_days=3,
        estimated_savings_inr=2800.0,
        reason="FEFO expiry mitigation + Tier-2 flu surge stockout prevention",
        status="RECOMMENDED"
    )
    session.add(trf1)
    await session.flush()

    # Seed Alerts with Small Numbers
    alerts = [
        Alert(
            id="ALT-20260824-001",
            alert_type="STOCKOUT_RISK",
            severity="critical",
            sku="P-1042",
            product_name="Paracetamol 500mg",
            warehouse_id="PAT-01",
            detail="Projected stockout in 3.2 days based on sensed flu surge demand (Stock: 25 units).",
            cause="Tier-2 demand spiked +62% while stock is at 25 units.",
            recommended_action="Execute recommended transfer TRF-20260824-001 from MUM-01 (120 units).",
            owner="Aditi Rao (SCM Planner)",
            status="New",
            escalation_level=1,
            escalation_due_at=now_utc + timedelta(hours=4),
            is_escalated=False
        ),
        Alert(
            id="ALT-20260824-002",
            alert_type="LOW_STOCK",
            severity="critical",
            sku="P-1042",
            product_name="Paracetamol 500mg",
            warehouse_id="BLR-01",
            detail="Current stock (180) is below configured reorder point (250).",
            cause="Regular consumption exceeded inbound receipts.",
            recommended_action="Approve Purchase Order for 150 units from HealthGen Pharma.",
            owner="Aditi Rao (SCM Planner)",
            status="New",
            escalation_level=1,
            escalation_due_at=now_utc + timedelta(hours=4),
            is_escalated=False
        ),
        Alert(
            id="ALT-20260824-003",
            alert_type="EXPIRY_RISK",
            severity="warning",
            sku="C-5562",
            product_name="Cough Syrup 100ml",
            warehouse_id="MUM-01",
            detail="Batch BAT-C-5562-MUM-01 (140 units) will expire in 22 days.",
            cause="Slow local dispensing in Mumbai DC.",
            recommended_action="Expedite FEFO transfer to high-demand North DC (DEL-02).",
            owner="Rohan Mehta (Warehouse Mgr)",
            status="New",
            escalation_level=2,
            escalation_due_at=now_utc + timedelta(hours=24),
            is_escalated=False
        ),
        Alert(
            id="ALT-20260824-004",
            alert_type="DEMAND_SURGE",
            severity="warning",
            sku="A-2381",
            product_name="Amoxicillin 250mg",
            warehouse_id="DEL-02",
            detail="Demand sensed surge of +28% in the last 3 days.",
            cause="Seasonal respiratory infection spike in Delhi NCR.",
            recommended_action="Increase replenishment frequency from 14d to 7d.",
            owner="Aditi Rao (SCM Planner)",
            status="Acknowledged",
            escalation_level=2,
            escalation_due_at=now_utc + timedelta(hours=24),
            is_escalated=False
        ),
        Alert(
            id="ALT-20260824-005",
            alert_type="STOCKOUT",
            severity="critical",
            sku="AZ-3391",
            product_name="Azithromycin 500mg",
            warehouse_id="HYD-01",
            detail="Stock is completely depleted (0 units). Inbound PO of 50 units in transit.",
            cause="Distributor backorders cleared remaining stock.",
            recommended_action="Expedite delivery with MediSupplies Ltd.",
            owner="Sara Iyer (Procurement Lead)",
            status="New",
            escalation_level=3,
            escalation_due_at=now_utc + timedelta(hours=2),
            is_escalated=True
        )
    ]
    session.add_all(alerts)
    await session.flush()

    # Seed Notification Logs
    notifications = [
        NotificationLog(
            alert_id="ALT-20260824-001",
            channel="EMAIL",
            recipient="aditi.rao@medcarepharma.com",
            subject="[CRITICAL SCM ALERT] Paracetamol 500mg Stockout Imminent in PAT-01",
            message_body="Demand surge detected. Available stock (25 units) covers only 3.2 days. Recommended action: Approve transfer from MUM-01 (120 units).",
            status="SENT",
            timestamp=now_utc - timedelta(minutes=45)
        ),
        NotificationLog(
            alert_id="ALT-20260824-001",
            channel="WHATSAPP",
            recipient="+91-9876543210 (Aditi Rao)",
            subject="MedCare Control Tower Alert",
            message_body="🚨 *CRITICAL SCM ALERT*: Paracetamol 500mg at PAT-01 will stock out in 3.2 days (25 units left). 1-click approve transfer on Control Tower: https://controltower.medcare.com/replenishment",
            status="DELIVERED",
            timestamp=now_utc - timedelta(minutes=44)
        ),
        NotificationLog(
            alert_id="ALT-20260824-003",
            channel="SMS",
            recipient="+91-9876543211 (Rohan Mehta)",
            subject="Expiry Alert",
            message_body="MedCare Alert: Batch BAT-C-5562-MUM-01 expires in 22 days (140 units). Review FEFO allocation.",
            status="DELIVERED",
            timestamp=now_utc - timedelta(minutes=30)
        )
    ]
    session.add_all(notifications)
    await session.flush()

    # Seed Demand Signals
    demand_signals = [
        DemandSignal(
            id="SIG-FLU-PATNA-2026",
            sku="P-1042",
            warehouse_id="PAT-01",
            signal_type="SEASONALITY",
            title="Seasonal Flu Wave Surge",
            description="Epidemiological surveillance indicates +60% spike in viral fever & influenza across Bihar & Eastern UP.",
            impact_pct=60.0,
            confidence_pct=94.0,
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=28),
            is_active=True,
            source="National Health Surveillance & Regional Hospital OPD Trends"
        ),
        DemandSignal(
            id="SIG-MONSOON-RESP-2026",
            sku="C-5562",
            warehouse_id="MUM-01",
            signal_type="WEATHER_EVENT",
            title="Monsoon Respiratory Wave",
            description="Heavy rainfall patterns driving +40% increase in pediatric & adult cough formulations.",
            impact_pct=40.0,
            confidence_pct=88.0,
            start_date=today - timedelta(days=14),
            end_date=today + timedelta(days=21),
            is_active=True,
            source="Meteorological Advisory & Pharmacy Retail POS"
        ),
        DemandSignal(
            id="SIG-PROMO-DIABETES-2026",
            sku="M-5521",
            warehouse_id="BLR-01",
            signal_type="PROMOTION",
            title="Annual Chronic Care Adherence Campaign",
            description="15% discount bundle on Metformin 500mg for retail pharmacy chains driving volume lift.",
            impact_pct=25.0,
            confidence_pct=91.0,
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=30),
            is_active=True,
            source="Commercial Sales Operations & Distributor Contracts"
        ),
        DemandSignal(
            id="SIG-HOLIDAY-DIWALI-2026",
            sku="A-2381",
            warehouse_id="DEL-02",
            signal_type="HOLIDAY",
            title="Pre-Festive Stock Build",
            description="Hospital networks stockpiling 2 weeks of essential antibiotics ahead of regional transport shutdowns.",
            impact_pct=35.0,
            confidence_pct=86.0,
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=21),
            is_active=True,
            source="Institutional Hospital Procurement Calendar"
        ),
        DemandSignal(
            id="SIG-STOCKOUT-HIST-2026",
            sku="AZ-3391",
            warehouse_id="HYD-01",
            signal_type="STOCKOUT_HISTORY",
            title="Unfulfilled Demand Velocity Rebound",
            description="Historical stockout in HYD-01 created backorder queue of 75 units releasing upon receipt.",
            impact_pct=45.0,
            confidence_pct=96.0,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=15),
            is_active=True,
            source="Distributor Backorder Ledger"
        ),
        DemandSignal(
            id="SIG-PRICE-REVISION-2026",
            sku="V-1122",
            warehouse_id="CHE-01",
            signal_type="PRICE_CHANGE",
            title="GST Rate Rationalization Impact",
            description="5% retail price reduction boosting institutional wellness clinic procurement.",
            impact_pct=15.0,
            confidence_pct=82.0,
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=60),
            is_active=True,
            source="Regulatory Pricing Authority & SCM Billing"
        )
    ]
    session.add_all(demand_signals)
    await session.flush()

    # Seed Escalations
    escalations = [
        AlertEscalation(
            id="ESC-20260824-001",
            alert_id="ALT-20260824-001",
            from_level=1,
            to_level=2,
            assigned_to="Rajesh Sharma (Regional SCM Director - East)",
            reason="Tier-2 DC PAT-01 stockout imminent in 3.2 days under +60% flu surge. Stock is down to 25 units.",
            action_taken="Expedited inter-DC stock balancing transfer from Mumbai DC (MUM-01) scheduled for dispatch (120 units).",
            sla_deadline=now_utc + timedelta(hours=4),
            escalated_at=now_utc - timedelta(minutes=40),
            status="IN_PROGRESS"
        ),
        AlertEscalation(
            id="ESC-20260824-002",
            alert_id="ALT-20260824-005",
            from_level=2,
            to_level=3,
            assigned_to="Dr. Vikram Malhotra (VP Global Supply Chain)",
            reason="Complete stockout of critical antibiotic Azithromycin (AZ-3391) at Hyderabad DC. Supplier lead-time delayed by 2 days.",
            action_taken="Emergency procurement override issued to MediSupplies Ltd with air courier dispatch (50 units).",
            sla_deadline=now_utc + timedelta(hours=2),
            escalated_at=now_utc - timedelta(minutes=25),
            status="IN_PROGRESS"
        ),
        AlertEscalation(
            id="ESC-20260824-003",
            alert_id="ALT-20260824-003",
            from_level=1,
            to_level=2,
            assigned_to="Priya Nair (QA & FEFO Regulatory Manager)",
            reason="Batch BAT-C-5562-MUM-01 with 140 units expires in 22 days. Requires immediate FEFO allocation.",
            action_taken="Authorized promotional markdown and expedited routing to Delhi NCR DC (DEL-02).",
            sla_deadline=now_utc + timedelta(hours=8),
            escalated_at=now_utc - timedelta(minutes=15),
            status="RESOLVED"
        )
    ]
    session.add_all(escalations)
    await session.flush()

    # Seed Sales Orders with Small Values
    sales_orders = [
        SalesOrder(
            id="SO-20260824-001",
            order_number="ORD-HOSP-9901",
            sku="P-1042",
            warehouse_id="MUM-01",
            quantity=40,
            unit_price=25.0,
            total_price=1000.0,
            customer_name="Apollo Hospitals Mumbai",
            channel="Hospital",
            status="COMPLETED",
            created_at=now_utc - timedelta(hours=3)
        ),
        SalesOrder(
            id="SO-20260824-002",
            order_number="ORD-DIST-8842",
            sku="A-2381",
            warehouse_id="DEL-02",
            quantity=25,
            unit_price=65.0,
            total_price=1625.0,
            customer_name="Fortis Healthcare Delhi",
            channel="Hospital",
            status="COMPLETED",
            created_at=now_utc - timedelta(hours=5)
        ),
        SalesOrder(
            id="SO-20260824-003",
            order_number="ORD-RETL-7721",
            sku="C-5562",
            warehouse_id="BLR-01",
            quantity=20,
            unit_price=75.0,
            total_price=1500.0,
            customer_name="MedPlus Pharmacy Retail",
            channel="Retail Pharmacy",
            status="COMPLETED",
            created_at=now_utc - timedelta(hours=6)
        ),
        SalesOrder(
            id="SO-20260824-004",
            order_number="ORD-HOSP-6632",
            sku="M-5521",
            warehouse_id="HYD-01",
            quantity=50,
            unit_price=30.0,
            total_price=1500.0,
            customer_name="Max Super Speciality Hospital",
            channel="Hospital",
            status="COMPLETED",
            created_at=now_utc - timedelta(hours=8)
        )
    ]
    session.add_all(sales_orders)
    await session.flush()

    # Seed System Settings
    settings_entries = [
        SystemSetting(key="service_level_pct", category="Inventory", value="95", description="Target customer service level percentage"),
        SystemSetting(key="safety_stock_method", category="Inventory", value="Service Level Based (95%)", description="Safety stock calculation model"),
        SystemSetting(key="reorder_point_method", category="Inventory", value="Demand During Lead Time + Safety Stock", description="Reorder point calculation model"),
        SystemSetting(key="expiry_critical_days", category="Inventory", value="30", description="Days threshold for critical expiry"),
        SystemSetting(key="expiry_at_risk_days", category="Inventory", value="90", description="Days threshold for at-risk expiry"),
        SystemSetting(key="expiry_watch_days", category="Inventory", value="180", description="Days threshold for watch expiry"),
        SystemSetting(key="forecast_horizon_days", category="Demand", value="30", description="Standard planning forecast horizon in days"),
        SystemSetting(key="forecast_model", category="Demand", value="Prophet (Holiday + Seasonality) + Sensed Velocity", description="Active ML demand sensing algorithm"),
        SystemSetting(key="lead_time_buffer_days", category="Replenishment", value="2", description="Buffer added to supplier lead times"),
        SystemSetting(key="auto_approve_threshold_inr", category="Replenishment", value="10000", description="Automatic replenishment PO approval threshold in INR"),
        SystemSetting(key="manager_approval_threshold_inr", category="Replenishment", value="50000", description="Manager sign-off threshold in INR"),
        SystemSetting(key="transfer_first_policy", category="Replenishment", value="Enabled", description="Always evaluate feasible network transfers before new procurement")
    ]
    session.add_all(settings_entries)
    await session.commit()
    print("[Seeder] Database successfully populated with realistic MedCare Pharma data (small values)!")


async def reset_and_seed_db():
    await init_database()
    async with AsyncSessionLocal() as session:
        await seed_database(session, force=True)


if __name__ == "__main__":
    asyncio.run(reset_and_seed_db())


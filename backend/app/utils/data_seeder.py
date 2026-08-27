import asyncio
from datetime import datetime, date, timedelta, timezone
import random
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func

from backend.app.database import AsyncSessionLocal, engine, Base, init_database
from backend.app.models import (
    Product, Warehouse, Inventory, Batch, InventoryTransaction,
    DemandHistory, DistributorOrder, SeasonalEvent, Promotion,
    ForecastRecord, DemandSurgeEvent, InventoryRisk,
    ReplenishmentRecommendation, PurchaseOrder, InventoryTransfer,
    Alert, NotificationLog, Scenario, ScenarioResult, SystemSetting,
    DemandSignal, AlertEscalation, SalesOrder,
    User, Role, Permission, RolePermission, AuditLog, Supplier
)
from backend.app.services.auth_service import AuthService
from backend.app.engines.inventory_engine import InventoryEngine

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


# Exactly 5 Warehouses across India
WAREHOUSES_DATA = [
    {"id": "MUM-01", "name": "Mumbai Central DC", "location": "Bhiwandi, Maharashtra", "tier": "Mother DC", "region": "West", "capacity_units": 350000, "current_utilization_pct": 81.4, "health_score": 94, "status": "Healthy", "is_active": True, "map_x": 30, "map_y": 55},
    {"id": "DEL-02", "name": "Delhi NCR DC", "location": "Kundli, Haryana", "tier": "Tier-1 DC", "region": "North", "capacity_units": 280000, "current_utilization_pct": 78.5, "health_score": 88, "status": "Healthy", "is_active": True, "map_x": 42, "map_y": 25},
    {"id": "BLR-01", "name": "Bengaluru South DC", "location": "Hosur Road, Karnataka", "tier": "Tier-1 DC", "region": "South", "capacity_units": 240000, "current_utilization_pct": 79.2, "health_score": 86, "status": "Healthy", "is_active": True, "map_x": 38, "map_y": 75},
    {"id": "PAT-01", "name": "Patna Regional DC", "location": "Fatuha, Bihar", "tier": "Tier-2 DC", "region": "East", "capacity_units": 180000, "current_utilization_pct": 65.5, "health_score": 75, "status": "At Risk", "is_active": True, "map_x": 72, "map_y": 38},
    {"id": "HYD-01", "name": "Hyderabad Regional DC", "location": "Medchal, Telangana", "tier": "Tier-2 DC", "region": "South", "capacity_units": 160000, "current_utilization_pct": 68.7, "health_score": 80, "status": "Healthy", "is_active": True, "map_x": 46, "map_y": 58}
]

# Exactly 5 Suppliers
SUPPLIERS_DATA = [
    {"id": "SUPP-001", "name": "Sun Pharma Labs", "contact_email": "orders@sunpharma.example.com", "contact_phone": "+91 98200 11223", "lead_time_days": 5, "category": "Analgesics, Antibiotics, Gastro Care", "status": "Active", "is_active": True},
    {"id": "SUPP-002", "name": "Cipla Healthcare", "contact_email": "dispatch@cipla.example.com", "contact_phone": "+91 98300 44556", "lead_time_days": 4, "category": "Respiratory, Cough & Cold, Anti-Infectives", "status": "Active", "is_active": True},
    {"id": "SUPP-003", "name": "Dr. Reddy's Laboratories", "contact_email": "supply@drreddys.example.com", "contact_phone": "+91 98400 77889", "lead_time_days": 6, "category": "Diabetes Care, Cardiovascular, Chronic Care", "status": "Active", "is_active": True},
    {"id": "SUPP-004", "name": "Lupin Pharmaceuticals", "contact_email": "orders@lupin.example.com", "contact_phone": "+91 98100 99001", "lead_time_days": 7, "category": "Antibiotics, Pain Management, Vitamins", "status": "Active", "is_active": True},
    {"id": "SUPP-005", "name": "Biocon Biologics", "contact_email": "coldchain@biocon.example.com", "contact_phone": "+91 98800 33445", "lead_time_days": 4, "category": "Cold-Chain, Insulin, Specialty Biologics", "status": "Active", "is_active": True}
]

# Exactly 20 Essential Pharmaceutical SKUs across 8 Therapeutic Categories
# Total target network stock VALUE ~ Rs. 9.36 Lakhs (<= Rs. 10 Lakh / 1,000,000 cap)
PRODUCTS_DATA = [
    # 1. Analgesics & Antipyretics
    {"sku": "P-1042", "name": "Paracetamol 500mg", "category": "Analgesics", "criticality": "Critical", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 1500, "default_safety_stock": 600, "moq": 100, "unit_cost": 25.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-001", "target_network_stock": 3000},
    {"sku": "P-1065", "name": "Paracetamol 650mg", "category": "Analgesics", "criticality": "Critical", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 1000, "default_safety_stock": 400, "moq": 100, "unit_cost": 30.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-001", "target_network_stock": 2000},
    {"sku": "IBU-400", "name": "Ibuprofen 400mg", "category": "Analgesics", "criticality": "High", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 200, "default_safety_stock": 80, "moq": 100, "unit_cost": 35.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-004", "target_network_stock": 1200},
    
    # 2. Antibiotics & Anti-Infectives
    {"sku": "A-2381", "name": "Amoxicillin 250mg", "category": "Antibiotics", "criticality": "Critical", "unit": "Strips", "shelf_life_days": 540, "default_reorder_point": 800, "default_safety_stock": 350, "moq": 100, "unit_cost": 60.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-001", "target_network_stock": 1000},
    {"sku": "AZ-3391", "name": "Azithromycin 500mg", "category": "Antibiotics", "criticality": "Critical", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 80, "default_safety_stock": 30, "moq": 50, "unit_cost": 120.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-002", "target_network_stock": 450},
    {"sku": "CIP-500", "name": "Ciprofloxacin 500mg", "category": "Antibiotics", "criticality": "High", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 120, "default_safety_stock": 50, "moq": 50, "unit_cost": 55.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-004", "target_network_stock": 650},
    
    # 3. Cough & Cold
    {"sku": "C-5562", "name": "Cough Syrup 100ml", "category": "Cough & Cold", "criticality": "High", "unit": "Bottles", "shelf_life_days": 730, "default_reorder_point": 140, "default_safety_stock": 60, "moq": 50, "unit_cost": 70.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-002", "target_network_stock": 750},
    {"sku": "CET-10", "name": "Cetirizine 10mg", "category": "Cough & Cold", "criticality": "Medium", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 350, "default_safety_stock": 150, "moq": 100, "unit_cost": 18.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-002", "target_network_stock": 2000},
    
    # 4. Respiratory
    {"sku": "S-1120", "name": "Salbutamol Inhaler", "category": "Respiratory", "criticality": "Critical", "unit": "Inhalers", "shelf_life_days": 730, "default_reorder_point": 60, "default_safety_stock": 25, "moq": 30, "unit_cost": 150.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-002", "target_network_stock": 300},
    {"sku": "BUD-200", "name": "Budesonide Respules 0.5mg", "category": "Respiratory", "criticality": "Critical", "unit": "Ampoules", "shelf_life_days": 540, "default_reorder_point": 50, "default_safety_stock": 20, "moq": 30, "unit_cost": 180.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-002", "target_network_stock": 240},
    
    # 5. Diabetes Care
    {"sku": "M-5521", "name": "Metformin 500mg", "category": "Diabetes Care", "criticality": "High", "unit": "Strips", "shelf_life_days": 1095, "default_reorder_point": 400, "default_safety_stock": 160, "moq": 100, "unit_cost": 30.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-003", "target_network_stock": 2400},
    {"sku": "GLI-2", "name": "Glimepiride 2mg", "category": "Diabetes Care", "criticality": "High", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 150, "default_safety_stock": 60, "moq": 50, "unit_cost": 45.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-003", "target_network_stock": 800},
    {"sku": "INS-100", "name": "Human Insulin 100IU", "category": "Diabetes Care", "criticality": "Critical", "unit": "Vials", "shelf_life_days": 540, "default_reorder_point": 30, "default_safety_stock": 15, "moq": 20, "unit_cost": 300.0, "is_temperature_sensitive": True, "is_active": True, "supplier_id": "SUPP-005", "target_network_stock": 150},
    
    # 6. Gastro Care
    {"sku": "O-3341", "name": "Omeprazole 20mg", "category": "Gastro Care", "criticality": "Medium", "unit": "Capsules", "shelf_life_days": 730, "default_reorder_point": 160, "default_safety_stock": 70, "moq": 50, "unit_cost": 40.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-001", "target_network_stock": 900},
    {"sku": "PAN-40", "name": "Pantoprazole 40mg", "category": "Gastro Care", "criticality": "High", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 200, "default_safety_stock": 80, "moq": 50, "unit_cost": 50.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-001", "target_network_stock": 1100},
    
    # 7. Cardiovascular
    {"sku": "ATV-10", "name": "Atorvastatin 10mg", "category": "Cardiovascular", "criticality": "High", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 130, "default_safety_stock": 50, "moq": 50, "unit_cost": 65.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-003", "target_network_stock": 700},
    {"sku": "AML-5", "name": "Amlodipine 5mg", "category": "Cardiovascular", "criticality": "Medium", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 250, "default_safety_stock": 100, "moq": 50, "unit_cost": 28.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-003", "target_network_stock": 1300},
    {"sku": "TEL-40", "name": "Telmisartan 40mg", "category": "Cardiovascular", "criticality": "High", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 130, "default_safety_stock": 50, "moq": 50, "unit_cost": 55.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-003", "target_network_stock": 750},
    
    # 8. Vitamins & Minerals
    {"sku": "V-1122", "name": "Vitamin C 500mg", "category": "Vitamins", "criticality": "Low", "unit": "Strips", "shelf_life_days": 730, "default_reorder_point": 400, "default_safety_stock": 160, "moq": 100, "unit_cost": 20.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-004", "target_network_stock": 2200},
    {"sku": "VD3-60K", "name": "Vitamin D3 60,000 IU", "category": "Vitamins", "criticality": "Medium", "unit": "Capsules", "shelf_life_days": 730, "default_reorder_point": 80, "default_safety_stock": 30, "moq": 50, "unit_cost": 80.0, "is_temperature_sensitive": False, "is_active": True, "supplier_id": "SUPP-004", "target_network_stock": 450}
]

# Warehouse distribution ratios (Total = 1.0)
# MUM-01: 30%, DEL-02: 23%, BLR-01: 20%, PAT-01: 15%, HYD-01: 12%
WH_DISTRIBUTION_WEIGHTS = {
    "MUM-01": 0.30,
    "DEL-02": 0.23,
    "BLR-01": 0.20,
    "PAT-01": 0.15,
    "HYD-01": 0.12
}


async def seed_auth_data(session: AsyncSession, force: bool = False):
    """Seeds roles, permissions, role-permission mappings, and initial users."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

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

    role_perms_res = await session.execute(select(RolePermission))
    existing_rp = {(rp.role_id, rp.permission_id) for rp in role_perms_res.scalars().all()}

    manager_restricted_perms = {
        "inventory.create_product", "inventory.delete_product", "forecast.train", "warehouses.manage",
        "users.view", "users.create", "users.edit", "users.deactivate",
        "users.reset_password", "users.assign_role", "audit.view",
        "system.configuration", "system.database", "system.migrations", "system.data_management"
    }

    new_mappings = []
    for p_data in PERMISSIONS_DATA:
        p_id = p_data["id"]
        if ("ADMIN", p_id) not in existing_rp:
            new_mappings.append(RolePermission(role_id="ADMIN", permission_id=p_id))
        if p_id not in manager_restricted_perms and ("MANAGER", p_id) not in existing_rp:
            new_mappings.append(RolePermission(role_id="MANAGER", permission_id=p_id))

    if new_mappings:
        session.add_all(new_mappings)
        await session.flush()

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
    print("[Seeder] Auth & RBAC roles, permissions, and users synchronized.")


async def seed_database(session: AsyncSession, force: bool = False):
    """
    Seed fresh, synthetic dataset into PostgreSQL:
    - 5 Warehouses
    - 5 Suppliers
    - 20 SKUs
    - Live Inventory Stock VALUE sum <= Rs. 10 Lakh (Rs. 1,000,000 monetary cap)
    - 180 Days of rich historical demand time-series for ML training
    - Clean reference data and settings
    """
    print("[Seeder] Checking database initialization...")
    today = date(2026, 8, 24)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if not force:
        # Check if database is already populated
        existing_wh = (await session.execute(select(func.count(Warehouse.id)))).scalar()
        existing_sku = (await session.execute(select(func.count(Product.sku)))).scalar()
        if existing_wh and existing_wh > 0 and existing_sku and existing_sku > 0:
            print(f"[Seeder] Database already populated ({existing_wh} warehouses, {existing_sku} SKUs). Skipping re-seed.")
            await seed_auth_data(session, force=False)
            return

    # 1. Clear existing data if force is requested
    if force:
        print("[Seeder] Force clear requested. Truncating transactional & master tables...")
        # Clear in reverse FK dependency order
        for model in [
            ScenarioResult, Scenario, NotificationLog, AlertEscalation, Alert,
            InventoryTransfer, PurchaseOrder, ReplenishmentRecommendation,
            InventoryRisk, DemandSurgeEvent, ForecastRecord,
            DemandSignal, Promotion, SeasonalEvent, DistributorOrder, DemandHistory,
            SalesOrder, InventoryTransaction, Batch, Inventory, Product, Warehouse, Supplier,
            SystemSetting, AuditLog
        ]:
            await session.execute(delete(model))
        await session.flush()

    # 2. Seed Auth
    await seed_auth_data(session, force=force)

    # 3. Seed Suppliers (5 suppliers)
    print("[Seeder] Seeding 5 Suppliers...")
    suppliers = [Supplier(**s) for s in SUPPLIERS_DATA]
    session.add_all(suppliers)
    await session.flush()

    # 4. Seed Warehouses (5 warehouses)
    print("[Seeder] Seeding 5 Warehouses...")
    warehouses = [Warehouse(**w) for w in WAREHOUSES_DATA]
    session.add_all(warehouses)
    await session.flush()

    # 5. Seed Products (20 SKUs)
    print("[Seeder] Seeding 20 Products/SKUs...")
    products = []
    for p in PRODUCTS_DATA:
        p_clean = {k: v for k, v in p.items() if k not in ["target_network_stock", "supplier_id"]}
        products.append(Product(**p_clean))
    session.add_all(products)
    await session.flush()

    # 6. Seed Inventory & Batches (Strictly <= Rs. 10 Lakh total monetary stock value)
    print("[Seeder] Seeding Live Inventory & Batches across 5 DCs (Target Stock Value: ~Rs. 9.36 Lakhs)...")
    batches_to_add = []
    inventory_to_add = []
    transactions_to_add = []

    total_units_seeded = 0
    total_value_seeded = 0.0

    for prod in PRODUCTS_DATA:
        sku = prod["sku"]
        net_target = prod["target_network_stock"]
        unit_cost = prod["unit_cost"]

        for wh in WAREHOUSES_DATA:
            wh_id = wh["id"]
            wh_weight = WH_DISTRIBUTION_WEIGHTS[wh_id]
            node_target_stock = int(round(net_target * wh_weight))

            # Operational variations for realistic supply chain dynamics:
            # 1. P-1042 in MUM-01: Excess stock with near-expiry batch (200 units)
            # 2. P-1042 in PAT-01: Critical low stock (25 units) to trigger restock/transfer
            # 3. AZ-3391 in HYD-01: Critical low stock / high demand
            # 4. C-5562 in MUM-01: Batch expiring in 30 days
            
            res_stock = 0
            inbound = 0
            
            if sku == "P-1042" and wh_id == "MUM-01":
                curr_stock = node_target_stock
                near_exp_qty = 200
                active_qty = curr_stock - near_exp_qty
                b1 = Batch(id=f"BAT-{sku}-MUM-01-EXP", sku=sku, warehouse_id=wh_id, quantity=near_exp_qty, reserved_quantity=0, mfg_date=today - timedelta(days=685), expiry_date=today + timedelta(days=45), status="NEAR_EXPIRY")
                b2 = Batch(id=f"BAT-{sku}-MUM-02-ACT", sku=sku, warehouse_id=wh_id, quantity=active_qty, reserved_quantity=0, mfg_date=today - timedelta(days=90), expiry_date=today + timedelta(days=640), status="ACTIVE")
                batches_to_add.extend([b1, b2])
                status = "OVERSTOCK"
                risk_level = "low"
                doc = 45.0

            elif sku == "P-1042" and wh_id == "PAT-01":
                # Critical stock for demo transfer scenario
                curr_stock = 25
                res_stock = 0
                b1 = Batch(id=f"BAT-{sku}-PAT-01", sku=sku, warehouse_id=wh_id, quantity=curr_stock, reserved_quantity=0, mfg_date=today - timedelta(days=120), expiry_date=today + timedelta(days=610), status="ACTIVE")
                batches_to_add.append(b1)
                status = "CRITICAL"
                risk_level = "critical"
                doc = 2.5

            elif sku == "C-5562" and wh_id == "MUM-01":
                curr_stock = node_target_stock
                near_exp_qty = 60
                active_qty = curr_stock - near_exp_qty
                b1 = Batch(id=f"BAT-{sku}-MUM-01-EXP", sku=sku, warehouse_id=wh_id, quantity=near_exp_qty, reserved_quantity=0, mfg_date=today - timedelta(days=700), expiry_date=today + timedelta(days=30), status="CRITICAL")
                b2 = Batch(id=f"BAT-{sku}-MUM-02-ACT", sku=sku, warehouse_id=wh_id, quantity=active_qty, reserved_quantity=0, mfg_date=today - timedelta(days=60), expiry_date=today + timedelta(days=670), status="ACTIVE")
                batches_to_add.extend([b1, b2])
                status = "HEALTHY"
                risk_level = "low"
                doc = 28.0

            elif sku == "AZ-3391" and wh_id == "HYD-01":
                curr_stock = 8
                inbound = 30
                b1 = Batch(id=f"BAT-{sku}-HYD-01", sku=sku, warehouse_id=wh_id, quantity=curr_stock, reserved_quantity=0, mfg_date=today - timedelta(days=90), expiry_date=today + timedelta(days=640), status="ACTIVE")
                batches_to_add.append(b1)
                status = "LOW_STOCK"
                risk_level = "high"
                doc = 8.0

            else:
                curr_stock = node_target_stock
                # Generate 1 or 2 standard active batches
                if curr_stock > 300:
                    split_1 = int(curr_stock * 0.6)
                    split_2 = curr_stock - split_1
                    b1 = Batch(id=f"BAT-{sku}-{wh_id}-A", sku=sku, warehouse_id=wh_id, quantity=split_1, reserved_quantity=0, mfg_date=today - timedelta(days=60), expiry_date=today + timedelta(days=670), status="ACTIVE")
                    b2 = Batch(id=f"BAT-{sku}-{wh_id}-B", sku=sku, warehouse_id=wh_id, quantity=split_2, reserved_quantity=0, mfg_date=today - timedelta(days=30), expiry_date=today + timedelta(days=700), status="ACTIVE")
                    batches_to_add.extend([b1, b2])
                else:
                    b1 = Batch(id=f"BAT-{sku}-{wh_id}-A", sku=sku, warehouse_id=wh_id, quantity=curr_stock, reserved_quantity=0, mfg_date=today - timedelta(days=45), expiry_date=today + timedelta(days=685), status="ACTIVE")
                    batches_to_add.extend([b1, b2])

                status = "HEALTHY"
                risk_level = "low"
                doc = round(curr_stock / max(1.0, (prod["default_reorder_point"] * wh_weight / 10)), 1)

            total_units_seeded += curr_stock
            total_value_seeded += curr_stock * unit_cost

            node_rop = int(round(prod["default_reorder_point"] * wh_weight))
            node_ss = int(round(prod["default_safety_stock"] * wh_weight))
            dyn_status, dyn_risk = InventoryEngine.evaluate_inventory_status(curr_stock, node_rop, node_ss)

            inv = Inventory(
                sku=sku,
                warehouse_id=wh_id,
                current_stock=curr_stock,
                reserved_stock=res_stock,
                inbound_stock=inbound,
                reorder_point=node_rop,
                safety_stock=node_ss,
                status=dyn_status,
                risk_level=dyn_risk,
                days_of_cover=doc,
                last_recalculated_at=now_utc
            )
            inventory_to_add.append(inv)

            # Baseline transaction receipt
            tx = InventoryTransaction(
                transaction_type="RECEIPT",
                sku=sku,
                warehouse_id=wh_id,
                quantity=curr_stock,
                previous_stock=0,
                new_stock=curr_stock,
                reference_id=f"INIT-STOCK-{wh_id}-{sku}",
                reason="Initial baseline stock replenishment",
                performed_by="System Seeder",
                timestamp=now_utc - timedelta(days=10)
            )
            transactions_to_add.append(tx)

    session.add_all(batches_to_add)
    session.add_all(inventory_to_add)
    session.add_all(transactions_to_add)
    await session.flush()
    print(f"[Seeder] Total live inventory: {total_units_seeded:,} units across {len(inventory_to_add)} nodes | Total Value: Rs. {total_value_seeded:,.2f} ({total_value_seeded/100000:.2f} Lakhs, Cap: <= Rs. 10 Lakh).")

    # 7. Seed Seasonal Events & Promotions
    print("[Seeder] Seeding Seasonal Events & Promotions...")
    seasonal_events = [
        SeasonalEvent(
            name="Annual Flu & Viral Infection Wave",
            event_type="Seasonal",
            start_date=today - timedelta(days=15),
            end_date=today + timedelta(days=60),
            impact_level="High",
            expected_uplift_pct=50.0,
            impacted_categories="Analgesics,Cough & Cold,Respiratory,Antibiotics",
            impacted_region="All"
        ),
        SeasonalEvent(
            name="Monsoon Vector & Gastro Illness Surge",
            event_type="Seasonal",
            start_date=today - timedelta(days=45),
            end_date=today + timedelta(days=15),
            impact_level="Medium",
            expected_uplift_pct=25.0,
            impacted_categories="Antibiotics,Gastro Care",
            impacted_region="West,South,East"
        ),
        SeasonalEvent(
            name="Winter Chronic Care Preventive Build",
            event_type="Seasonal",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=120),
            impact_level="Medium",
            expected_uplift_pct=20.0,
            impacted_categories="Diabetes Care,Cardiovascular,Vitamins",
            impacted_region="North,East"
        )
    ]
    promotions = [
        Promotion(
            name="Institutional Immunity Health Pack Promotion",
            sku="V-1122",
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            expected_uplift_pct=25.0,
            discount_pct=15.0
        ),
        Promotion(
            name="Chronic Disease Adherence Campaign",
            sku="M-5521",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            expected_uplift_pct=20.0,
            discount_pct=10.0
        )
    ]
    session.add_all(seasonal_events)
    session.add_all(promotions)
    await session.flush()

    # 8. Seed 180 Days of Historical Demand Data for ML Training
    print("[Seeder] Generating 180 Days of Synthetic Time-Series Demand History for ML training...")
    demand_records = []
    
    # 180 days history: from (today - 180d) to (today - 1d)
    for day_offset in range(180, 0, -1):
        record_date = today - timedelta(days=day_offset)
        dow = record_date.weekday()
        # Day of week multiplier (Mon-Fri higher demand)
        dow_factor = 1.12 if dow in [0, 1, 2, 3, 4] else (0.90 if dow == 5 else 0.75)
        trend_factor = 1.0 + (180 - day_offset) * 0.0003  # slight gentle upward growth

        for prod in PRODUCTS_DATA:
            sku = prod["sku"]
            cat = prod["category"]
            # Network daily base sales proportional to SKU total stock volume (~30 days turnover)
            daily_base_network = max(2.0, prod["target_network_stock"] / 32.0)

            for wh in WAREHOUSES_DATA:
                wh_id = wh["id"]
                wh_factor = WH_DISTRIBUTION_WEIGHTS[wh_id]
                
                # Check seasonal event uplifts
                seasonal_boost = 1.0
                if cat in ["Analgesics", "Cough & Cold", "Respiratory", "Antibiotics"] and day_offset <= 45:
                    seasonal_boost += 0.45  # Flu surge
                if cat in ["Antibiotics", "Gastro Care"] and (60 <= day_offset <= 120):
                    seasonal_boost += 0.20  # Monsoon surge

                # Random gaussian noise
                noise = np.random.normal(1.0, 0.06)
                daily_sales = max(1, int(round(daily_base_network * wh_factor * dow_factor * trend_factor * seasonal_boost * noise)))

                # Unfulfilled demand for low stock periods
                unfulfilled = 0
                if sku == "P-1042" and wh_id == "PAT-01" and day_offset <= 7:
                    unfulfilled = int(daily_sales * 0.20)
                elif sku == "AZ-3391" and wh_id == "HYD-01" and day_offset <= 10:
                    unfulfilled = int(daily_sales * 0.25)

                dh = DemandHistory(
                    sku=sku,
                    warehouse_id=wh_id,
                    date=record_date,
                    actual_sales=daily_sales,
                    unfulfilled_demand=unfulfilled,
                    channel="Hospital" if dow in [0, 2, 4] else "Distributor",
                    region=wh["region"]
                )
                demand_records.append(dh)

    # Batch insert demand history
    session.add_all(demand_records)
    await session.flush()
    print(f"[Seeder] Generated {len(demand_records):,} historical demand time-series records.")

    # 9. Seed Demand Signals (Multi-factor sensing overlays)
    print("[Seeder] Seeding Live Demand Signals...")
    demand_signals = [
        DemandSignal(
            id="SIG-FLU-EAST-2026",
            sku="P-1042",
            warehouse_id="PAT-01",
            signal_type="SEASONALITY",
            title="Regional Flu & Viral Fever Outbreak",
            description="Epidemiological hospital OPD trends show +50% surge in viral fever across Eastern territories.",
            impact_pct=50.0,
            confidence_pct=94.0,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=35),
            is_active=True,
            source="National Health Surveillance & OPD Registry"
        ),
        DemandSignal(
            id="SIG-RESP-NORTH-2026",
            sku="C-5562",
            warehouse_id="DEL-02",
            signal_type="WEATHER_EVENT",
            title="Monsoon Respiratory Wave",
            description="High air humidity and rainfall driving +40% increase in prescription cough formulations.",
            impact_pct=40.0,
            confidence_pct=89.0,
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
            title="Chronic Disease Adherence Campaign",
            description="Institutional hospital network bulk ordering for diabetic adherence program.",
            impact_pct=25.0,
            confidence_pct=92.0,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            is_active=True,
            source="Commercial Sales Operations"
        ),
        DemandSignal(
            id="SIG-ANTIBIOTIC-WEST-2026",
            sku="A-2381",
            warehouse_id="MUM-01",
            signal_type="HOLIDAY",
            title="Pre-Festive Stock Build",
            description="Hospital networks stockpiling 2 weeks of essential broad-spectrum antibiotics.",
            impact_pct=30.0,
            confidence_pct=87.0,
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=21),
            is_active=True,
            source="Institutional Hospital Procurement Calendar"
        )
    ]
    session.add_all(demand_signals)
    await session.flush()

    # 10. Seed Initial System Settings
    print("[Seeder] Seeding SCM System Settings...")
    settings_entries = [
        SystemSetting(key="service_level_pct", category="Inventory", value="95", description="Target customer service level percentage"),
        SystemSetting(key="safety_stock_method", category="Inventory", value="Service Level Based (95%)", description="Safety stock calculation model"),
        SystemSetting(key="reorder_point_method", category="Inventory", value="Demand During Lead Time + Safety Stock", description="Reorder point calculation model"),
        SystemSetting(key="expiry_critical_days", category="Inventory", value="30", description="Days threshold for critical expiry"),
        SystemSetting(key="expiry_at_risk_days", category="Inventory", value="90", description="Days threshold for at-risk expiry"),
        SystemSetting(key="expiry_watch_days", category="Inventory", value="180", description="Days threshold for watch expiry"),
        SystemSetting(key="forecast_horizon_days", category="Demand", value="30", description="Standard planning forecast horizon in days"),
        SystemSetting(key="forecast_model", category="Demand", value="RandomForestRegressor (Multi-Signal Sensing)", description="Active ML demand sensing algorithm"),
        SystemSetting(key="lead_time_buffer_days", category="Replenishment", value="2", description="Buffer added to supplier lead times"),
        SystemSetting(key="auto_approve_threshold_inr", category="Replenishment", value="100000", description="Automatic replenishment PO approval threshold in INR"),
        SystemSetting(key="manager_approval_threshold_inr", category="Replenishment", value="500000", description="Manager sign-off threshold in INR"),
        SystemSetting(key="transfer_first_policy", category="Replenishment", value="Enabled", description="Always evaluate feasible network transfers before new procurement")
    ]
    session.add_all(settings_entries)
    await session.flush()

    # 11. Seed Initial Active Inter-DC Transfer Recommendation (FEFO Near-Expiry MUM-01 -> PAT-01)
    trf1 = InventoryTransfer(
        id="TRF-P-1042-MUM-01-PAT-01-20260824",
        sku="P-1042",
        source_warehouse_id="MUM-01",
        destination_warehouse_id="PAT-01",
        batch_id="BAT-P-1042-MUM-01-EXP",
        quantity=100,
        available_at_source=200,
        transfer_lead_time_days=3,
        estimated_savings_inr=2500.0,
        reason="FEFO expiry mitigation: Transfer near-expiry batch (45d) from Mumbai Mother DC to high-demand Patna Regional DC",
        status="RECOMMENDED"
    )
    session.add(trf1)

    rec1 = ReplenishmentRecommendation(
        id="REC-20260824-001",
        sku="P-1042",
        warehouse_id="PAT-01",
        current_stock=25,
        forecast_demand_30d=450.0,
        safety_stock=30,
        recommended_quantity=100,
        recommended_frequency="Every 7 days (Surge Cadence)",
        next_review_date=today + timedelta(days=7),
        decision_type="TRANSFER",
        preferred_source="MUM-01",
        estimated_cost_inr=2500.0,
        priority="critical",
        reason_what="Transfer 100 units of Paracetamol 500mg from MUM-01 to PAT-01",
        reason_why="PAT-01 has surging flu demand (25 units remaining). MUM-01 has 200 units expiring in 45 days.",
        reason_when="Transfer immediately (dispatch today, arrival in 3 days).",
        reason_impact="Eliminates immediate stockout risk in East DC and prevents expiry write-off in MUM-01.",
        status="PENDING",
        requested_by="P1 Demand Sensing Engine"
    )
    rec2 = ReplenishmentRecommendation(
        id="REC-20260824-002",
        sku="AZ-3391",
        warehouse_id="HYD-01",
        current_stock=18,
        forecast_demand_30d=65.0,
        safety_stock=4,
        recommended_quantity=50,
        recommended_frequency="Every 14 days",
        next_review_date=today + timedelta(days=14),
        decision_type="REPLENISH",
        preferred_source="Cipla Healthcare",
        estimated_cost_inr=6000.0,
        priority="critical",
        reason_what="Procure 50 units from Cipla Healthcare",
        reason_why="Stock is below reorder point (18 units vs ROP 10) and demand is trending upward.",
        reason_when="Order within 24 hours.",
        reason_impact="Restores safety stock cover to 25 days.",
        status="PENDING",
        requested_by="E1 Restock Engine"
    )
    session.add_all([rec1, rec2])

    # Initial Alerts
    alert1 = Alert(
        id="ALT-20260824-001",
        alert_type="STOCKOUT_RISK",
        severity="critical",
        sku="P-1042",
        product_name="Paracetamol 500mg",
        warehouse_id="PAT-01",
        detail="Projected stockout in 2.5 days based on sensed flu surge demand in East DC.",
        cause="Eastern territory demand spiked +50% under seasonal outbreak.",
        recommended_action="Execute recommended transfer TRF-P-1042-MUM-01-PAT-01-20260824 from MUM-01 (100 units).",
        owner="Dr. Aditi Rao (SCM Lead)",
        status="New",
        escalation_level=1,
        escalation_due_at=now_utc + timedelta(hours=4),
        is_escalated=False
    )
    alert2 = Alert(
        id="ALT-20260824-002",
        alert_type="EXPIRY_RISK",
        severity="warning",
        sku="C-5562",
        product_name="Cough Syrup 100ml",
        warehouse_id="MUM-01",
        detail="Batch BAT-C-5562-MUM-01-EXP (60 bottles) expires in 30 days.",
        cause="Local consumption velocity in Mumbai Mother DC is lower than batch allocation.",
        recommended_action="Expedite FEFO transfer to Delhi NCR DC (DEL-02).",
        owner="Rohan Mehta (Warehouse Mgr)",
        status="New",
        escalation_level=2,
        escalation_due_at=now_utc + timedelta(hours=24),
        is_escalated=False
    )
    session.add_all([alert1, alert2])

    await session.commit()
    print("[Seeder] Database reset and re-seed with clean synthetic dataset (Stock Value <= Rs. 10 Lakh) completed successfully!")


async def reset_and_seed_db():
    await init_database()
    async with AsyncSessionLocal() as session:
        await seed_database(session, force=True)


if __name__ == "__main__":
    asyncio.run(reset_and_seed_db())

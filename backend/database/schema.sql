-- ============================================================================
-- MedCare Pharma SCM Control Tower - Complete Unified PostgreSQL DDL Schema
-- Matches 100% with SQLAlchemy ORM models in backend/app/models/
-- Generated: 2026-08-24
-- ============================================================================

-- Drop existing tables in reverse dependency order if needed for clean re-creation
-- DROP TABLE IF EXISTS scenario_results CASCADE;
-- DROP TABLE IF EXISTS scenarios CASCADE;
-- DROP TABLE IF EXISTS notifications CASCADE;
-- DROP TABLE IF EXISTS escalations CASCADE;
-- DROP TABLE IF EXISTS alerts CASCADE;
-- DROP TABLE IF EXISTS inventory_transfers CASCADE;
-- DROP TABLE IF EXISTS purchase_orders CASCADE;
-- DROP TABLE IF EXISTS replenishment_recommendations CASCADE;
-- DROP TABLE IF EXISTS inventory_risk CASCADE;
-- DROP TABLE IF EXISTS demand_surge_events CASCADE;
-- DROP TABLE IF EXISTS forecasts CASCADE;
-- DROP TABLE IF EXISTS demand_signals CASCADE;
-- DROP TABLE IF EXISTS promotions CASCADE;
-- DROP TABLE IF EXISTS seasonal_events CASCADE;
-- DROP TABLE IF EXISTS distributor_orders CASCADE;
-- DROP TABLE IF EXISTS demand_history CASCADE;
-- DROP TABLE IF EXISTS sales_orders CASCADE;
-- DROP TABLE IF EXISTS inventory_transactions CASCADE;
-- DROP TABLE IF EXISTS batches CASCADE;
-- DROP TABLE IF EXISTS inventory CASCADE;
-- DROP TABLE IF EXISTS products CASCADE;
-- DROP TABLE IF EXISTS warehouses CASCADE;
-- DROP TABLE IF EXISTS system_settings CASCADE;

-- 1. System Settings
CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(80) PRIMARY KEY,
    category VARCHAR(50) DEFAULT 'General',
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- 1b. Suppliers (Vendors & Manufacturers)
CREATE TABLE IF NOT EXISTS suppliers (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    contact_email VARCHAR(120),
    contact_phone VARCHAR(50),
    lead_time_days INTEGER DEFAULT 5,
    category VARCHAR(150),
    status VARCHAR(30) DEFAULT 'Active',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_suppliers_name ON suppliers(name);

-- 2. Warehouses (Multi-Tier Distribution Centers)
CREATE TABLE IF NOT EXISTS warehouses (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    tier VARCHAR(50) DEFAULT 'Tier-2 DC',
    region VARCHAR(50) DEFAULT 'West',
    capacity_units INTEGER DEFAULT 50000,
    current_utilization_pct DOUBLE PRECISION DEFAULT 65.0,
    health_score INTEGER DEFAULT 95,
    status VARCHAR(20) DEFAULT 'Healthy',
    is_active BOOLEAN DEFAULT TRUE,
    map_x INTEGER DEFAULT 50,
    map_y INTEGER DEFAULT 50,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- 3. Products Master Catalog
CREATE TABLE IF NOT EXISTS products (
    sku VARCHAR(50) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    criticality VARCHAR(20) DEFAULT 'Medium',
    unit VARCHAR(20) DEFAULT 'Units',
    shelf_life_days INTEGER NOT NULL,
    default_reorder_point INTEGER NOT NULL,
    default_safety_stock INTEGER NOT NULL,
    moq INTEGER DEFAULT 1000,
    unit_cost DOUBLE PRECISION NOT NULL,
    is_temperature_sensitive BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_products_category ON products(category);

-- Ensure is_active columns exist on existing tables
ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 4. Inventory Node Stocks
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    current_stock INTEGER NOT NULL DEFAULT 0,
    reserved_stock INTEGER NOT NULL DEFAULT 0,
    inbound_stock INTEGER NOT NULL DEFAULT 0,
    reorder_point INTEGER NOT NULL,
    safety_stock INTEGER NOT NULL,
    status VARCHAR(30) DEFAULT 'HEALTHY',
    risk_level VARCHAR(20) DEFAULT 'low',
    days_of_cover DOUBLE PRECISION DEFAULT 0.0,
    last_recalculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    CONSTRAINT uq_sku_warehouse UNIQUE (sku, warehouse_id)
);
CREATE INDEX IF NOT EXISTS ix_inventory_sku ON inventory(sku);
CREATE INDEX IF NOT EXISTS ix_inventory_wh ON inventory(warehouse_id);

-- 5. Batches (FEFO Tracking)
CREATE TABLE IF NOT EXISTS batches (
    id VARCHAR(50) PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    reserved_quantity INTEGER DEFAULT 0,
    mfg_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status VARCHAR(30) DEFAULT 'ACTIVE',
    is_quarantined BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_batches_sku ON batches(sku);
CREATE INDEX IF NOT EXISTS ix_batches_expiry ON batches(expiry_date);

-- 6. Inventory Transactions Audit Trail
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id SERIAL PRIMARY KEY,
    transaction_type VARCHAR(30) NOT NULL,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    batch_id VARCHAR(50),
    quantity INTEGER NOT NULL,
    previous_stock INTEGER NOT NULL,
    new_stock INTEGER NOT NULL,
    reference_id VARCHAR(100),
    reason TEXT,
    performed_by VARCHAR(80) DEFAULT 'System',
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_inv_tx_sku ON inventory_transactions(sku);
CREATE INDEX IF NOT EXISTS ix_inv_tx_wh ON inventory_transactions(warehouse_id);
CREATE INDEX IF NOT EXISTS ix_inv_tx_timestamp ON inventory_transactions(timestamp);

-- 7. Sales Orders (Prescriptions & Customer Orders)
CREATE TABLE IF NOT EXISTS sales_orders (
    id VARCHAR(50) PRIMARY KEY,
    order_number VARCHAR(80) NOT NULL UNIQUE,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total_price DOUBLE PRECISION NOT NULL,
    customer_name VARCHAR(150) NOT NULL,
    channel VARCHAR(50) DEFAULT 'Hospital',
    status VARCHAR(30) DEFAULT 'COMPLETED',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_sales_orders_sku ON sales_orders(sku);
CREATE INDEX IF NOT EXISTS ix_sales_orders_created ON sales_orders(created_at);

-- 8. Demand History
CREATE TABLE IF NOT EXISTS demand_history (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    actual_sales INTEGER DEFAULT 0,
    unfulfilled_demand INTEGER DEFAULT 0,
    channel VARCHAR(50) DEFAULT 'Distributor',
    region VARCHAR(50) DEFAULT 'South'
);
CREATE INDEX IF NOT EXISTS ix_demand_history_sku_wh_date ON demand_history(sku, warehouse_id, date);

-- 9. Distributor Orders
CREATE TABLE IF NOT EXISTS distributor_orders (
    id VARCHAR(50) PRIMARY KEY,
    distributor_name VARCHAR(120) NOT NULL,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    region VARCHAR(50) NOT NULL,
    order_quantity INTEGER NOT NULL,
    order_date DATE NOT NULL,
    required_date DATE NOT NULL,
    priority VARCHAR(20) DEFAULT 'Normal',
    status VARCHAR(30) DEFAULT 'PENDING',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- 10. Seasonal Events & Promotions
CREATE TABLE IF NOT EXISTS seasonal_events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) DEFAULT 'Seasonal',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    impact_level VARCHAR(20) DEFAULT 'High',
    expected_uplift_pct DOUBLE PRECISION DEFAULT 60.0,
    impacted_categories VARCHAR(200) DEFAULT 'Analgesics,Cough & Cold,Respiratory',
    impacted_region VARCHAR(100) DEFAULT 'All'
);

CREATE TABLE IF NOT EXISTS promotions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    expected_uplift_pct DOUBLE PRECISION DEFAULT 20.0,
    discount_pct DOUBLE PRECISION DEFAULT 10.0
);

-- 11. Demand Signals (Multi-Factor Sensing Overlays)
CREATE TABLE IF NOT EXISTS demand_signals (
    id VARCHAR(50) PRIMARY KEY,
    sku VARCHAR(50) REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) REFERENCES warehouses(id) ON DELETE CASCADE,
    signal_type VARCHAR(50) NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    impact_pct DOUBLE PRECISION DEFAULT 0.0,
    confidence_pct DOUBLE PRECISION DEFAULT 85.0,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    source VARCHAR(100) DEFAULT 'ML Demand Sensing Engine',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_demand_signals_dates ON demand_signals(start_date, end_date);

-- 12. Forecast Records & Demand Surge Events
CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    forecast_date DATE NOT NULL,
    baseline_demand DOUBLE PRECISION DEFAULT 0.0,
    sensed_demand DOUBLE PRECISION DEFAULT 0.0,
    final_forecast DOUBLE PRECISION NOT NULL,
    lower_bound DOUBLE PRECISION DEFAULT 0.0,
    upper_bound DOUBLE PRECISION DEFAULT 0.0,
    confidence_pct DOUBLE PRECISION DEFAULT 87.0,
    trend_direction VARCHAR(20) DEFAULT 'Increasing',
    primary_driver VARCHAR(100) DEFAULT 'Flu Season Surge',
    generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_forecasts_sku_wh_date ON forecasts(sku, warehouse_id, forecast_date);

CREATE TABLE IF NOT EXISTS demand_surge_events (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    normal_demand DOUBLE PRECISION NOT NULL,
    recent_sensed_demand DOUBLE PRECISION NOT NULL,
    surge_pct DOUBLE PRECISION NOT NULL,
    severity VARCHAR(20) DEFAULT 'HIGH',
    detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    status VARCHAR(30) DEFAULT 'ACTIVE',
    explanation TEXT
);

-- 13. Inventory Risk
CREATE TABLE IF NOT EXISTS inventory_risk (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    current_inventory INTEGER NOT NULL,
    daily_sensed_demand DOUBLE PRECISION NOT NULL,
    days_of_cover DOUBLE PRECISION NOT NULL,
    lead_time_days INTEGER DEFAULT 5,
    safety_stock INTEGER DEFAULT 2500,
    stockout_risk_score DOUBLE PRECISION DEFAULT 0.0,
    stockout_risk_level VARCHAR(20) DEFAULT 'low',
    estimated_stockout_date DATE,
    near_expiry_units INTEGER DEFAULT 0,
    expiry_risk_score DOUBLE PRECISION DEFAULT 0.0,
    expiry_risk_level VARCHAR(20) DEFAULT 'low',
    risk_summary TEXT,
    calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_risk_sku_wh ON inventory_risk(sku, warehouse_id);

-- 14. Replenishment Recommendations & Purchase Orders
CREATE TABLE IF NOT EXISTS replenishment_recommendations (
    id VARCHAR(50) PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    current_stock INTEGER NOT NULL,
    forecast_demand_30d DOUBLE PRECISION NOT NULL,
    safety_stock INTEGER NOT NULL,
    recommended_quantity INTEGER NOT NULL,
    recommended_frequency VARCHAR(50) DEFAULT 'Every 14 days',
    next_review_date DATE NOT NULL,
    decision_type VARCHAR(30) DEFAULT 'REPLENISH',
    preferred_source VARCHAR(50) DEFAULT 'SUPPLIER',
    estimated_cost_inr DOUBLE PRECISION DEFAULT 0.0,
    priority VARCHAR(20) DEFAULT 'medium',
    reason_what TEXT,
    reason_why TEXT,
    reason_when TEXT,
    reason_impact TEXT,
    status VARCHAR(30) DEFAULT 'PENDING',
    requested_by VARCHAR(80) DEFAULT 'SCM Engine',
    approved_by VARCHAR(80),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id VARCHAR(50) PRIMARY KEY,
    recommendation_id VARCHAR(50),
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    supplier_name VARCHAR(120) DEFAULT 'HealthGen Pharma',
    quantity INTEGER NOT NULL,
    unit_cost_inr DOUBLE PRECISION DEFAULT 50.0,
    total_cost_inr DOUBLE PRECISION DEFAULT 0.0,
    order_date DATE NOT NULL,
    eta_date DATE NOT NULL,
    status VARCHAR(30) DEFAULT 'Sent',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- 15. Inter-DC Inventory Transfers
CREATE TABLE IF NOT EXISTS inventory_transfers (
    id VARCHAR(50) PRIMARY KEY,
    sku VARCHAR(50) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    source_warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    destination_warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    batch_id VARCHAR(50),
    quantity INTEGER NOT NULL,
    available_at_source INTEGER NOT NULL,
    transfer_lead_time_days INTEGER DEFAULT 3,
    estimated_savings_inr DOUBLE PRECISION DEFAULT 0.0,
    reason TEXT,
    status VARCHAR(30) DEFAULT 'RECOMMENDED',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    dispatched_at TIMESTAMP WITHOUT TIME ZONE,
    received_at TIMESTAMP WITHOUT TIME ZONE
);

-- 16. Alerts & SLA Escalations
CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(50) PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    sku VARCHAR(50) REFERENCES products(sku) ON DELETE SET NULL,
    product_name VARCHAR(150),
    warehouse_id VARCHAR(20) REFERENCES warehouses(id) ON DELETE SET NULL,
    detail TEXT NOT NULL,
    cause TEXT,
    recommended_action TEXT,
    owner VARCHAR(80) DEFAULT 'Supply Chain Planner',
    status VARCHAR(30) DEFAULT 'New',
    escalation_level INTEGER DEFAULT 1,
    escalation_due_at TIMESTAMP WITHOUT TIME ZONE,
    is_escalated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    acknowledged_at TIMESTAMP WITHOUT TIME ZONE,
    resolved_at TIMESTAMP WITHOUT TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS ix_alerts_severity ON alerts(severity);

CREATE TABLE IF NOT EXISTS escalations (
    id VARCHAR(50) PRIMARY KEY,
    alert_id VARCHAR(50) NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    from_level INTEGER DEFAULT 1,
    to_level INTEGER DEFAULT 2,
    assigned_to VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    action_taken TEXT,
    sla_deadline TIMESTAMP WITHOUT TIME ZONE,
    escalated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    resolved_at TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING'
);
CREATE INDEX IF NOT EXISTS ix_escalations_alert_id ON escalations(alert_id);

-- 17. Notification Logs
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(50) REFERENCES alerts(id) ON DELETE SET NULL,
    channel VARCHAR(30) NOT NULL,
    recipient VARCHAR(150) NOT NULL,
    subject VARCHAR(200),
    message_body TEXT NOT NULL,
    status VARCHAR(30) DEFAULT 'SENT',
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- 18. What-If Scenarios & Simulation Results
CREATE TABLE IF NOT EXISTS scenarios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    demand_change_pct DOUBLE PRECISION DEFAULT 20.0,
    lead_time_change_days INTEGER DEFAULT 3,
    starting_inventory_change_pct DOUBLE PRECISION DEFAULT 0.0,
    capacity_constraint_pct DOUBLE PRECISION DEFAULT 0.0,
    distributor_demand_change_pct DOUBLE PRECISION DEFAULT 0.0,
    category_filter VARCHAR(80) DEFAULT 'All',
    warehouse_filter VARCHAR(50) DEFAULT 'All',
    status VARCHAR(30) DEFAULT 'Completed',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS scenario_results (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    projected_stockout_skus INTEGER DEFAULT 0,
    stockout_value_inr DOUBLE PRECISION DEFAULT 0.0,
    stockout_value_formatted VARCHAR(50) DEFAULT '₹0.0 Cr',
    avg_service_level_pct DOUBLE PRECISION DEFAULT 85.0,
    total_replenishment_need_inr DOUBLE PRECISION DEFAULT 0.0,
    total_replenishment_formatted VARCHAR(50) DEFAULT '₹0.0 Cr',
    inventory_holding_cost_inr DOUBLE PRECISION DEFAULT 0.0,
    obsolete_expiry_risk_inr DOUBLE PRECISION DEFAULT 0.0,
    impact_trend_json JSON,
    affected_skus_json JSON,
    comparison_metrics_json JSON,
    calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_scenario_results_scenario_id ON scenario_results(scenario_id);

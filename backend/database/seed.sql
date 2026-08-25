-- ============================================================================
-- MedCare Pharma SCM Control Tower - Clean, Human-Understandable Learnable Dataset
-- Purpose: 3 Distribution Centers, 10 Core Products, Clean Traceable Numbers
-- Generated: 2026-08-24
-- ============================================================================

-- Clean existing data for clean reload
TRUNCATE TABLE scenario_results, scenarios, notifications, escalations, alerts, 
               inventory_transfers, purchase_orders, replenishment_recommendations, 
               inventory_risk, demand_surge_events, forecasts, demand_signals, 
               promotions, seasonal_events, distributor_orders, demand_history, 
               sales_orders, inventory_transactions, batches, inventory, 
               products, warehouses, system_settings RESTART IDENTITY CASCADE;

-- 1. System Settings
INSERT INTO system_settings (key, category, value, description) VALUES
('service_level_pct', 'Inventory', '95', 'Target customer service level percentage'),
('safety_stock_method', 'Inventory', 'Service Level Based (95%)', 'Safety stock calculation model'),
('reorder_point_method', 'Inventory', 'Demand During Lead Time + Safety Stock', 'Reorder point calculation model'),
('expiry_critical_days', 'Inventory', '30', 'Days threshold for critical expiry'),
('expiry_at_risk_days', 'Inventory', '60', 'Days threshold for at-risk expiry'),
('expiry_watch_days', 'Inventory', '90', 'Days threshold for watch expiry'),
('forecast_horizon_days', 'Demand', '30', 'Standard planning forecast horizon in days'),
('forecast_model', 'Demand', 'RandomForestRegressor (Multi-Signal Sensing)', 'Active ML demand algorithm'),
('lead_time_buffer_days', 'Replenishment', '2', 'Buffer added to supplier lead times'),
('auto_approve_threshold_inr', 'Replenishment', '50000', 'Automatic replenishment PO approval threshold in INR'),
('manager_approval_threshold_inr', 'Replenishment', '100000', 'Manager sign-off threshold in INR'),
('transfer_first_policy', 'Replenishment', 'Enabled', 'Always evaluate feasible network transfers before new procurement');

-- 2. Warehouses (3 Learnable DCs)
INSERT INTO warehouses (id, name, location, tier, region, capacity_units, current_utilization_pct, health_score, status, is_active, map_x, map_y) VALUES
('MUM-01', 'Mumbai Central DC', 'Bhiwandi, Maharashtra', 'Mother DC', 'West', 50000, 68.0, 94, 'Healthy', true, 30, 55),
('DEL-02', 'Delhi NCR DC', 'Kundli, Haryana', 'Tier-1 DC', 'North', 40000, 72.0, 75, 'At Risk', true, 42, 25),
('PAT-01', 'Patna Regional DC', 'Fatuha, Bihar', 'Tier-2 DC', 'East', 20000, 55.0, 60, 'At Risk', true, 72, 38);

-- 3. Products (10 Core Essential Medicines)
INSERT INTO products (sku, name, category, criticality, unit, shelf_life_days, default_reorder_point, default_safety_stock, moq, unit_cost, is_temperature_sensitive, is_active) VALUES
('P-1042', 'Paracetamol 500mg', 'Analgesics', 'Critical', 'Strips', 730, 1500, 800, 500, 25.0, false, true),
('P-1065', 'Paracetamol 650mg', 'Analgesics', 'Critical', 'Strips', 730, 1200, 600, 500, 30.0, false, true),
('A-2381', 'Amoxicillin 250mg', 'Antibiotics', 'Critical', 'Strips', 540, 1000, 500, 500, 60.0, false, true),
('AZ-3391', 'Azithromycin 500mg', 'Antibiotics', 'Critical', 'Strips', 730, 800, 400, 300, 120.0, false, true),
('C-5562', 'Cough Syrup 100ml', 'Cough & Cold', 'High', 'Bottles', 730, 1000, 500, 500, 70.0, false, true),
('M-5521', 'Metformin 500mg', 'Diabetes Care', 'High', 'Strips', 1095, 2000, 1000, 1000, 30.0, false, true),
('INS-100', 'Human Insulin 100IU', 'Diabetes Care', 'Critical', 'Vials', 540, 500, 250, 200, 300.0, true, true),
('O-3341', 'Omeprazole 20mg', 'Gastro Care', 'Medium', 'Capsules', 730, 800, 400, 400, 40.0, false, true),
('S-1120', 'Salbutamol Inhaler', 'Respiratory', 'Critical', 'Inhalers', 730, 400, 200, 200, 150.0, false, true),
('V-1122', 'Vitamin C 500mg', 'Vitamins', 'Low', 'Strips', 730, 1000, 500, 500, 20.0, false, true);

-- 4. Inventory Node Stocks (Clear Proportional Numbers)
INSERT INTO inventory (sku, warehouse_id, current_stock, reserved_stock, inbound_stock, reorder_point, safety_stock, status, risk_level, days_of_cover) VALUES
-- Mumbai Mother DC (Surplus Hub)
('P-1042', 'MUM-01', 5000, 200, 0, 1500, 800, 'OVERSTOCK', 'low', 50.0),
('P-1065', 'MUM-01', 3000, 100, 0, 1200, 600, 'HEALTHY', 'low', 35.0),
('A-2381', 'MUM-01', 2500, 100, 0, 1000, 500, 'HEALTHY', 'low', 30.0),
('AZ-3391', 'MUM-01', 1800, 100, 0, 800, 400, 'HEALTHY', 'low', 28.0),
('C-5562', 'MUM-01', 2500, 100, 0, 1000, 500, 'OVERSTOCK', 'low', 32.0),
('M-5521', 'MUM-01', 4000, 200, 0, 2000, 1000, 'HEALTHY', 'low', 40.0),
('INS-100', 'MUM-01', 800, 50, 0, 500, 250, 'HEALTHY', 'low', 26.0),
('O-3341', 'MUM-01', 1500, 50, 0, 800, 400, 'HEALTHY', 'low', 30.0),
('S-1120', 'MUM-01', 700, 50, 0, 400, 200, 'HEALTHY', 'low', 28.0),
('V-1122', 'MUM-01', 2000, 100, 0, 1000, 500, 'HEALTHY', 'low', 35.0),

-- Delhi NCR DC (North Tier-1 DC)
('P-1042', 'DEL-02', 2000, 100, 0, 1500, 800, 'HEALTHY', 'low', 25.0),
('P-1065', 'DEL-02', 1500, 50, 0, 1200, 600, 'HEALTHY', 'low', 20.0),
('A-2381', 'DEL-02', 800, 50, 0, 1000, 500, 'LOW_STOCK', 'high', 9.5),
('AZ-3391', 'DEL-02', 0, 0, 1000, 800, 400, 'OUT_OF_STOCK', 'critical', 0.0),
('C-5562', 'DEL-02', 600, 50, 0, 1000, 500, 'LOW_STOCK', 'high', 8.2),
('M-5521', 'DEL-02', 2500, 100, 0, 2000, 1000, 'HEALTHY', 'low', 30.0),
('INS-100', 'DEL-02', 400, 20, 0, 500, 250, 'HEALTHY', 'low', 18.0),
('O-3341', 'DEL-02', 900, 50, 0, 800, 400, 'HEALTHY', 'low', 20.0),
('S-1120', 'DEL-02', 350, 20, 0, 400, 200, 'LOW_STOCK', 'high', 9.0),
('V-1122', 'DEL-02', 1200, 50, 0, 1000, 500, 'HEALTHY', 'low', 24.0),

-- Patna Regional DC (East Tier-2 DC)
('P-1042', 'PAT-01', 250, 20, 0, 1500, 800, 'CRITICAL', 'critical', 3.2),
('P-1065', 'PAT-01', 400, 20, 0, 1200, 600, 'LOW_STOCK', 'high', 7.5),
('A-2381', 'PAT-01', 900, 50, 0, 1000, 500, 'HEALTHY', 'low', 18.0),
('AZ-3391', 'PAT-01', 600, 30, 0, 800, 400, 'HEALTHY', 'low', 15.0),
('C-5562', 'PAT-01', 800, 40, 0, 1000, 500, 'HEALTHY', 'low', 16.0),
('M-5521', 'PAT-01', 1800, 80, 0, 2000, 1000, 'HEALTHY', 'low', 22.0),
('INS-100', 'PAT-01', 150, 10, 0, 500, 250, 'CRITICAL', 'critical', 6.5),
('O-3341', 'PAT-01', 700, 30, 0, 800, 400, 'HEALTHY', 'low', 18.0),
('S-1120', 'PAT-01', 250, 10, 0, 400, 200, 'HEALTHY', 'low', 14.0),
('V-1122', 'PAT-01', 800, 30, 0, 1000, 500, 'HEALTHY', 'low', 20.0);

-- 5. Batches (FEFO Traceability)
INSERT INTO batches (id, sku, warehouse_id, quantity, reserved_quantity, mfg_date, expiry_date, status, is_quarantined) VALUES
('BAT-P-1042-MUM-01', 'P-1042', 'MUM-01', 4000, 0, '2024-10-15', '2026-10-08', 'NEAR_EXPIRY', false),
('BAT-P-1042-MUM-02', 'P-1042', 'MUM-01', 1000, 0, '2026-05-15', '2028-05-15', 'ACTIVE', false),
('BAT-P-1042-DEL-02', 'P-1042', 'DEL-02', 2000, 0, '2026-04-10', '2028-04-10', 'ACTIVE', false),
('BAT-P-1042-PAT-01', 'P-1042', 'PAT-01', 250, 0, '2026-03-20', '2028-03-20', 'ACTIVE', false),

('BAT-P-1065-MUM-01', 'P-1065', 'MUM-01', 3000, 0, '2026-02-15', '2028-02-15', 'ACTIVE', false),
('BAT-P-1065-DEL-02', 'P-1065', 'DEL-02', 1500, 0, '2026-02-15', '2028-02-15', 'ACTIVE', false),
('BAT-P-1065-PAT-01', 'P-1065', 'PAT-01', 400, 0, '2026-02-15', '2028-02-15', 'ACTIVE', false),

('BAT-C-5562-MUM-01', 'C-5562', 'MUM-01', 1500, 0, '2024-09-24', '2026-09-24', 'NEAR_EXPIRY', false),
('BAT-C-5562-MUM-02', 'C-5562', 'MUM-01', 1000, 0, '2026-06-15', '2028-06-15', 'ACTIVE', false),
('BAT-C-5562-DEL-02', 'C-5562', 'DEL-02', 600, 0, '2025-11-20', '2027-11-20', 'ACTIVE', false),
('BAT-C-5562-PAT-01', 'C-5562', 'PAT-01', 800, 0, '2026-01-10', '2028-01-10', 'ACTIVE', false),

('BAT-INS-100-MUM-01', 'INS-100', 'MUM-01', 800, 0, '2025-11-20', '2027-05-20', 'ACTIVE', false),
('BAT-INS-100-DEL-02', 'INS-100', 'DEL-02', 400, 0, '2025-11-20', '2027-05-20', 'ACTIVE', false),
('BAT-INS-100-PAT-01', 'INS-100', 'PAT-01', 150, 0, '2025-08-15', '2027-02-15', 'ACTIVE', false),

('BAT-A-2381-MUM-01', 'A-2381', 'MUM-01', 2500, 0, '2025-10-10', '2027-04-10', 'ACTIVE', false),
('BAT-A-2381-DEL-02', 'A-2381', 'DEL-02', 800, 0, '2025-10-10', '2027-04-10', 'ACTIVE', false),
('BAT-A-2381-PAT-01', 'A-2381', 'PAT-01', 900, 0, '2025-10-10', '2027-04-10', 'ACTIVE', false),

('BAT-AZ-3391-MUM-01', 'AZ-3391', 'MUM-01', 1800, 0, '2026-01-10', '2028-01-10', 'ACTIVE', false),
('BAT-AZ-3391-PAT-01', 'AZ-3391', 'PAT-01', 600, 0, '2025-10-15', '2027-10-15', 'ACTIVE', false);

-- 6. Demand Signals (4 Distinct Labeled Real-Time Overlays)
INSERT INTO demand_signals (id, sku, warehouse_id, signal_type, title, description, impact_pct, confidence_pct, start_date, end_date, is_active, source) VALUES
('SIG-FLU-PATNA-2026', 'P-1042', 'PAT-01', 'SEASONALITY', 'Regional Flu Wave Spike', 'Epidemiological OPD trends report +50% surge in viral fever across Patna & Eastern territories.', 50.0, 94.0, '2026-08-15', '2026-09-20', true, 'Regional Health Directorate & OPD Trend Data'),
('SIG-MONSOON-RESP-2026', 'C-5562', 'DEL-02', 'WEATHER_EVENT', 'Monsoon Respiratory Surge', 'High rainfall and humidity driving +40% increase in prescription cough formulations in North region.', 40.0, 88.0, '2026-08-10', '2026-09-15', true, 'Meteorological Health Advisory & Pharmacy POS'),
('SIG-PROMO-DIABETES-2026', 'M-5521', 'MUM-01', 'PROMOTION', 'Chronic Care Adherence Campaign', 'Special bundle discount on Metformin 500mg driving +25% volume lift across retail pharmacy partners.', 25.0, 92.0, '2026-08-20', '2026-09-25', true, 'Commercial Sales Operations'),
('SIG-FESTIVE-DIWALI-2026', 'A-2381', 'DEL-02', 'HOLIDAY', 'Pre-Festive Stock Build', 'Hospital networks stockpiling essential antibiotics ahead of regional holiday shutdowns.', 30.0, 85.0, '2026-08-25', '2026-09-10', true, 'Institutional Procurement Schedule');

-- 7. Inter-DC Transfers (FEFO Balancing Opportunities)
INSERT INTO inventory_transfers (id, sku, source_warehouse_id, destination_warehouse_id, batch_id, quantity, available_at_source, transfer_lead_time_days, estimated_savings_inr, reason, status) VALUES
('TRF-P-1042-MUM-PAT', 'P-1042', 'MUM-01', 'PAT-01', 'BAT-P-1042-MUM-01', 2000, 5000, 3, 45000.0, 'Patna DC stockout in 3.2 days under +50% flu surge. Mumbai Mother DC has 4,000 near-expiry units.', 'RECOMMENDED'),
('TRF-C-5562-MUM-DEL', 'C-5562', 'MUM-01', 'DEL-02', 'BAT-C-5562-MUM-01', 1000, 2500, 3, 25000.0, 'Delhi NCR DC stock below safety buffer (600 bottles). Mumbai has 1,500 near-expiry units.', 'RECOMMENDED');

-- 8. Replenishment Recommendations
INSERT INTO replenishment_recommendations (id, sku, warehouse_id, current_stock, forecast_demand_30d, safety_stock, recommended_quantity, recommended_frequency, next_review_date, decision_type, preferred_source, estimated_cost_inr, priority, reason_what, reason_why, reason_when, reason_impact, status) VALUES
('REC-P-1042-PAT-01', 'P-1042', 'PAT-01', 250, 1500.0, 800, 2000, 'Weekly', '2026-08-31', 'TRANSFER', 'MUM-01', 50000.0, 'critical', 'Transfer 2,000 units Paracetamol 500mg from MUM-01 to PAT-01', 'Patna DC stock covers only 3.2 days under +50% flu wave. Mumbai has 4,000 near-expiry units.', 'Execute within 24 hours', 'Prevents regional stockout, utilizes near-expiry batch, saves ₹45,000 in emergency procurement expense.', 'PENDING'),
('REC-AZ-3391-DEL-02', 'AZ-3391', 'DEL-02', 0, 800.0, 400, 1000, 'Immediate', '2026-08-25', 'REPLENISH', 'MediSupplies Ltd.', 120000.0, 'critical', 'Issue Purchase Order for 1,000 strips Azithromycin 500mg', 'Delhi NCR DC is completely out of stock with 500 units backorder queue.', 'Dispatch immediately via express logistics', 'Restores service level from 0% to 98% and satisfies pending hospital orders.', 'PENDING'),
('REC-INS-100-PAT-01', 'INS-100', 'PAT-01', 150, 400.0, 250, 300, 'Weekly', '2026-08-31', 'REPLENISH', 'BioPharma Global', 90000.0, 'critical', 'Procure 300 vials Human Insulin 100IU with temperature-controlled cold chain', 'Patna DC stock (150 vials) below critical safety buffer (250 vials).', 'Submit PO within 48 hours', 'Ensures uninterrupted supply for diabetic clinical care network.', 'PENDING'),
('REC-A-2381-DEL-02', 'A-2381', 'DEL-02', 800, 1200.0, 500, 800, 'Bi-Weekly', '2026-09-02', 'REPLENISH', 'HealthGen Pharma', 48000.0, 'high', 'Issue Purchase Order for 800 strips Amoxicillin 250mg', 'Delhi NCR DC stock (800 units) is below reorder point (1,000 units).', 'Submit PO by 26 Aug', 'Protects inventory buffer ahead of pre-festive demand build.', 'PENDING'),
('REC-C-5562-DEL-02', 'C-5562', 'DEL-02', 600, 1000.0, 500, 1000, 'Weekly', '2026-08-30', 'TRANSFER', 'MUM-01', 70000.0, 'high', 'Transfer 1,000 bottles Cough Syrup from Mumbai Mother DC to Delhi NCR DC', 'Delhi DC cover at 8.2 days under heavy monsoon prescription demand.', 'Execute within 48 hours', 'Elevates regional fill rate to 96% and minimizes emergency transport expense.', 'PENDING');

-- 9. Purchase Orders
INSERT INTO purchase_orders (id, sku, warehouse_id, supplier_name, quantity, unit_cost_inr, total_cost_inr, order_date, eta_date, status) VALUES
('PO-8841', 'P-1042', 'MUM-01', 'HealthGen Pharma', 3000, 25.0, 75000.0, '2026-08-22', '2026-08-27', 'Sent'),
('PO-8836', 'C-5562', 'DEL-02', 'Wellness Labs', 1000, 70.0, 70000.0, '2026-08-21', '2026-08-26', 'Sent'),
('PO-8829', 'AZ-3391', 'DEL-02', 'MediSupplies Ltd.', 1000, 120.0, 120000.0, '2026-08-18', '2026-08-24', 'Approved');

-- 10. Alerts (Clear 1-to-1 Cause and Effect)
INSERT INTO alerts (id, alert_type, severity, sku, product_name, warehouse_id, detail, cause, recommended_action, owner, status, escalation_level, is_escalated) VALUES
('ALT-001', 'STOCKOUT_RISK', 'critical', 'P-1042', 'Paracetamol 500mg', 'PAT-01', 'Current stock (250 units) will stock out in 3.2 days under sensed +50% flu surge.', 'Regional viral outbreak in Eastern territory (Bihar/UP).', 'Approve inter-DC transfer TRF-P-1042-MUM-PAT from Mumbai Mother DC.', 'Dr. Aditi Rao (Lead Demand Planner)', 'New', 2, true),
('ALT-002', 'STOCKOUT', 'critical', 'AZ-3391', 'Azithromycin 500mg', 'DEL-02', 'Stock is completely depleted (0 units). Backorder queue of 500 units pending.', 'High antibiotic demand cleared remaining stock; inbound PO-8829 in transit.', 'Expedite PO-8829 with MediSupplies Ltd via express air freight.', 'Dr. Aditi Rao (Lead Demand Planner)', 'New', 3, true),
('ALT-003', 'EXPIRY_RISK', 'medium', 'C-5562', 'Cough Syrup 100ml', 'MUM-01', 'Batch BAT-C-5562-MUM-01 with 1,500 units expires in 30 days.', 'Stock velocity in West zone is lower than production batch allocation.', 'FEFO rebalance transfer to Delhi NCR DC (DEL-02).', 'Priya Nair (QA & Regulatory)', 'Acknowledged', 2, true),
('ALT-004', 'LOW_STOCK', 'warning', 'A-2381', 'Amoxicillin 250mg', 'DEL-02', 'Current stock (800 units) is below dynamic reorder point (1,000 units).', 'Steady institutional hospital consumption run-rate.', 'Issue replenishment purchase order of 800 units.', 'Rohan Mehta (Regional SCM Manager)', 'New', 1, false),
('ALT-005', 'LOW_STOCK', 'warning', 'INS-100', 'Human Insulin 100IU', 'PAT-01', 'Current stock (150 vials) below safety stock threshold (250 vials).', 'Cold-chain transit delay on previous order cycle.', 'Expedite PO of 300 vials to BioPharma Global.', 'Dr. Aditi Rao (Lead Demand Planner)', 'New', 1, false),
('ALT-006', 'CAPACITY_WARNING', 'warning', NULL, 'General Formulations', 'DEL-02', 'Space utilization reached 72.0%, approaching warning threshold.', 'Advance seasonal buffer receipts.', 'Optimized rack arrangement and re-routed non-critical buffer pallets.', 'Vikram Nair (VP Global Supply Chain)', 'Resolved', 1, false);

-- 11. Alert Escalations
INSERT INTO escalations (id, alert_id, from_level, to_level, assigned_to, reason, action_taken, status) VALUES
('ESC-001', 'ALT-001', 1, 2, 'Rajesh Sharma (Regional SCM Director - East)', 'Patna DC stockout imminent in 3.2 days under +50% flu wave.', 'Expedited inter-DC stock balancing transfer TRF-P-1042-MUM-PAT scheduled.', 'IN_PROGRESS'),
('ESC-002', 'ALT-002', 2, 3, 'Dr. Vikram Malhotra (VP Global Supply Chain)', 'Complete stockout of critical antibiotic Azithromycin at Delhi DC.', 'Emergency procurement override issued to MediSupplies Ltd.', 'IN_PROGRESS'),
('ESC-003', 'ALT-006', 1, 1, 'Vikram Nair (North DC Operations Manager)', 'Space utilization alert resolved.', 'Re-routed 500 pallets to annex warehouse.', 'RESOLVED');

-- 12. Sales Orders (Recent Traceable Dispatches)
INSERT INTO sales_orders (id, order_number, sku, warehouse_id, quantity, unit_price, total_price, customer_name, channel, status) VALUES
('SO-001', 'ORD-HOSP-101', 'P-1042', 'MUM-01', 500, 25.0, 12500.0, 'Apollo Hospitals Mumbai', 'Hospital', 'COMPLETED'),
('SO-002', 'ORD-DIST-102', 'A-2381', 'DEL-02', 300, 60.0, 18000.0, 'Fortis Healthcare Delhi', 'Hospital', 'COMPLETED'),
('SO-003', 'ORD-RETL-103', 'C-5562', 'PAT-01', 200, 70.0, 14000.0, 'MedPlus Pharmacy Patna', 'Retail Pharmacy', 'COMPLETED'),
('SO-004', 'ORD-HOSP-104', 'M-5521', 'MUM-01', 500, 30.0, 15000.0, 'Max Super Speciality Mumbai', 'Hospital', 'COMPLETED'),
('SO-005', 'ORD-HOSP-105', 'INS-100', 'DEL-02', 100, 300.0, 30000.0, 'AIIMS Delhi', 'Hospital', 'COMPLETED');

-- 13. Inventory Transactions (Recent Audit Trail)
INSERT INTO inventory_transactions (transaction_type, sku, warehouse_id, quantity, previous_stock, new_stock, reference_id, reason, performed_by) VALUES
('SALE', 'P-1042', 'MUM-01', 500, 5500, 5000, 'ORD-HOSP-101', 'Hospital bulk order fulfillment', 'Sales Dispatch'),
('SALE', 'A-2381', 'DEL-02', 300, 1100, 800, 'ORD-DIST-102', 'Institutional hospital dispatch', 'Sales Dispatch'),
('RECEIPT', 'P-1042', 'MUM-01', 1000, 4000, 5000, 'GRN-20260824-01', 'Batch BAT-P-1042-MUM-02 received from HealthGen', 'Inbound Receiving'),
('TRANSFER_OUT', 'P-1042', 'MUM-01', 2000, 7000, 5000, 'TRF-P-1042-MUM-PAT', 'Inter-DC balancing for Patna flu wave', 'Rebalancing Lead');

-- 14. 30 Days of Historical Demand (Clean Traceable Numbers)
DO $$
DECLARE
    curr_date DATE := DATE '2026-07-25';
    end_date DATE := DATE '2026-08-24';
    sku_list TEXT[] := ARRAY['P-1042', 'P-1065', 'A-2381', 'AZ-3391', 'C-5562', 'M-5521', 'INS-100', 'O-3341', 'S-1120', 'V-1122'];
    wh_list TEXT[] := ARRAY['MUM-01', 'DEL-02', 'PAT-01'];
    curr_sku TEXT;
    curr_wh TEXT;
    base_sales INT;
    day_idx INT := 0;
    sales_val INT;
BEGIN
    WHILE curr_date <= end_date LOOP
        FOREACH curr_wh IN ARRAY wh_list LOOP
            FOREACH curr_sku IN ARRAY sku_list LOOP
                -- Deterministic, clean base daily sales
                IF curr_sku = 'P-1042' THEN
                    base_sales := 40;
                    IF curr_wh = 'PAT-01' AND curr_date >= DATE '2026-08-15' THEN
                        base_sales := 75; -- Flu wave surge
                    END IF;
                ELSIF curr_sku = 'P-1065' THEN
                    base_sales := 30;
                ELSIF curr_sku = 'A-2381' THEN
                    base_sales := 25;
                ELSIF curr_sku = 'AZ-3391' THEN
                    base_sales := 20;
                ELSIF curr_sku = 'C-5562' THEN
                    base_sales := 25;
                    IF curr_wh = 'DEL-02' AND curr_date >= DATE '2026-08-10' THEN
                        base_sales := 45; -- Monsoon surge
                    END IF;
                ELSIF curr_sku = 'M-5521' THEN
                    base_sales := 50;
                ELSIF curr_sku = 'INS-100' THEN
                    base_sales := 15;
                ELSIF curr_sku = 'O-3341' THEN
                    base_sales := 25;
                ELSIF curr_sku = 'S-1120' THEN
                    base_sales := 15;
                ELSE
                    base_sales := 30;
                END IF;

                -- Modest weekday variation (Monday/Friday slightly higher, weekend lower)
                IF EXTRACT(DOW FROM curr_date) IN (0, 6) THEN
                    sales_val := ROUND(base_sales * 0.7);
                ELSIF EXTRACT(DOW FROM curr_date) IN (1, 5) THEN
                    sales_val := ROUND(base_sales * 1.15);
                ELSE
                    sales_val := base_sales;
                END IF;

                INSERT INTO demand_history (sku, warehouse_id, date, actual_sales, unfulfilled_demand, channel, region)
                VALUES (
                    curr_sku, 
                    curr_wh, 
                    curr_date, 
                    sales_val, 
                    CASE WHEN curr_sku = 'AZ-3391' AND curr_wh = 'DEL-02' AND curr_date >= DATE '2026-08-20' THEN 15 ELSE 0 END,
                    'Hospital',
                    CASE WHEN curr_wh = 'MUM-01' THEN 'West' WHEN curr_wh = 'DEL-02' THEN 'North' ELSE 'East' END
                );
            END LOOP;
        END LOOP;
        curr_date := curr_date + INTERVAL '1 day';
    END LOOP;
END $$;

SELECT 'MedCare Pharma Small Learnable Dataset seeded successfully!' AS status;

-- ============================================================================
-- MedCare Pharma SCM Control Tower - Clean, Synthetic Dataset (5 DCs, 20 SKUs)
-- Purpose: 5 Distribution Centers, 5 Suppliers, 20 Core SKUs, Stock <= 10 Lakh Units, 180-Day ML History
-- Generated: 2026-08-26
-- ============================================================================

-- Clean existing data for clean reload
TRUNCATE TABLE scenario_results, scenarios, notifications, escalations, alerts, 
               inventory_transfers, purchase_orders, replenishment_recommendations, 
               inventory_risk, demand_surge_events, forecasts, demand_signals, 
               promotions, seasonal_events, distributor_orders, demand_history, 
               sales_orders, inventory_transactions, batches, inventory, 
               products, warehouses, suppliers, system_settings RESTART IDENTITY CASCADE;

-- 1. System Settings
INSERT INTO system_settings (key, category, value, description) VALUES
('service_level_pct', 'Inventory', '95', 'Target customer service level percentage'),
('safety_stock_method', 'Inventory', 'Service Level Based (95%)', 'Safety stock calculation model'),
('reorder_point_method', 'Inventory', 'Demand During Lead Time + Safety Stock', 'Reorder point calculation model'),
('expiry_critical_days', 'Inventory', '30', 'Days threshold for critical expiry'),
('expiry_at_risk_days', 'Inventory', '90', 'Days threshold for at-risk expiry'),
('expiry_watch_days', 'Inventory', '180', 'Days threshold for watch expiry'),
('forecast_horizon_days', 'Demand', '30', 'Standard planning forecast horizon in days'),
('forecast_model', 'Demand', 'RandomForestRegressor (Multi-Signal Sensing)', 'Active ML demand algorithm'),
('lead_time_buffer_days', 'Replenishment', '2', 'Buffer added to supplier lead times'),
('auto_approve_threshold_inr', 'Replenishment', '100000', 'Automatic replenishment PO approval threshold in INR'),
('manager_approval_threshold_inr', 'Replenishment', '500000', 'Manager sign-off threshold in INR'),
('transfer_first_policy', 'Replenishment', 'Enabled', 'Always evaluate feasible network transfers before new procurement');

-- 2. Suppliers (5 Suppliers)
INSERT INTO suppliers (id, name, contact_email, contact_phone, lead_time_days, category, status, is_active) VALUES
('SUPP-001', 'Sun Pharma Labs', 'orders@sunpharma.example.com', '+91 98200 11223', 5, 'Analgesics, Antibiotics, Gastro Care', 'Active', true),
('SUPP-002', 'Cipla Healthcare', 'dispatch@cipla.example.com', '+91 98300 44556', 4, 'Respiratory, Cough & Cold, Anti-Infectives', 'Active', true),
('SUPP-003', 'Dr. Reddy''s Laboratories', 'supply@drreddys.example.com', '+91 98400 77889', 6, 'Diabetes Care, Cardiovascular, Chronic Care', 'Active', true),
('SUPP-004', 'Lupin Pharmaceuticals', 'orders@lupin.example.com', '+91 98100 99001', 7, 'Antibiotics, Pain Management, Vitamins', 'Active', true),
('SUPP-005', 'Biocon Biologics', 'coldchain@biocon.example.com', '+91 98800 33445', 4, 'Cold-Chain, Insulin, Specialty Biologics', 'Active', true);

-- 3. Warehouses (5 Warehouses)
INSERT INTO warehouses (id, name, location, tier, region, capacity_units, current_utilization_pct, health_score, status, is_active, map_x, map_y) VALUES
('MUM-01', 'Mumbai Central DC', 'Bhiwandi, Maharashtra', 'Mother DC', 'West', 350000, 81.4, 94, 'Healthy', true, 30, 55),
('DEL-02', 'Delhi NCR DC', 'Kundli, Haryana', 'Tier-1 DC', 'North', 280000, 78.5, 88, 'Healthy', true, 42, 25),
('BLR-01', 'Bengaluru South DC', 'Hosur Road, Karnataka', 'Tier-1 DC', 'South', 240000, 79.2, 86, 'Healthy', true, 38, 75),
('KOL-01', 'Kolkata Eastern DC', 'Dankuni, West Bengal', 'Tier-1 DC', 'East', 200000, 72.5, 82, 'Healthy', true, 74, 45),
('HYD-01', 'Hyderabad Regional DC', 'Medchal, Telangana', 'Tier-2 DC', 'South', 160000, 68.7, 80, 'Healthy', true, 46, 58);

-- 4. Products (20 Core Essential SKUs)
INSERT INTO products (sku, name, category, criticality, unit, shelf_life_days, default_reorder_point, default_safety_stock, moq, unit_cost, is_temperature_sensitive, is_active) VALUES
('P-1042', 'Paracetamol 500mg', 'Analgesics', 'Critical', 'Strips', 730, 12000, 5000, 5000, 25.0, false, true),
('P-1065', 'Paracetamol 650mg', 'Analgesics', 'Critical', 'Strips', 730, 10000, 4000, 4000, 30.0, false, true),
('IBU-400', 'Ibuprofen 400mg', 'Analgesics', 'High', 'Strips', 730, 8000, 3000, 3000, 35.0, false, true),
('A-2381', 'Amoxicillin 250mg', 'Antibiotics', 'Critical', 'Strips', 540, 9000, 3500, 3000, 60.0, false, true),
('AZ-3391', 'Azithromycin 500mg', 'Antibiotics', 'Critical', 'Strips', 730, 7000, 2800, 2000, 120.0, false, true),
('CIP-500', 'Ciprofloxacin 500mg', 'Antibiotics', 'High', 'Strips', 730, 6000, 2500, 2000, 55.0, false, true),
('C-5562', 'Cough Syrup 100ml', 'Cough & Cold', 'High', 'Bottles', 730, 9000, 3500, 3000, 70.0, false, true),
('CET-10', 'Cetirizine 10mg', 'Cough & Cold', 'Medium', 'Strips', 730, 10000, 4000, 5000, 18.0, false, true),
('S-1120', 'Salbutamol Inhaler', 'Respiratory', 'Critical', 'Inhalers', 730, 3500, 1400, 1000, 150.0, false, true),
('BUD-200', 'Budesonide Respules 0.5mg', 'Respiratory', 'Critical', 'Ampoules', 540, 4000, 1500, 1000, 180.0, false, true),
('M-5521', 'Metformin 500mg', 'Diabetes Care', 'High', 'Strips', 1095, 14000, 6000, 5000, 30.0, false, true),
('GLI-2', 'Glimepiride 2mg', 'Diabetes Care', 'High', 'Strips', 730, 8000, 3000, 3000, 45.0, false, true),
('INS-100', 'Human Insulin 100IU', 'Diabetes Care', 'Critical', 'Vials', 540, 4000, 1500, 1000, 300.0, true, true),
('O-3341', 'Omeprazole 20mg', 'Gastro Care', 'Medium', 'Capsules', 730, 8000, 3000, 3000, 40.0, false, true),
('PAN-40', 'Pantoprazole 40mg', 'Gastro Care', 'High', 'Strips', 730, 11000, 4500, 4000, 50.0, false, true),
('ATV-10', 'Atorvastatin 10mg', 'Cardiovascular', 'High', 'Strips', 730, 10000, 4000, 4000, 65.0, false, true),
('AML-5', 'Amlodipine 5mg', 'Cardiovascular', 'Medium', 'Strips', 730, 9000, 3500, 4000, 28.0, false, true),
('TEL-40', 'Telmisartan 40mg', 'Cardiovascular', 'High', 'Strips', 730, 8500, 3200, 3000, 55.0, false, true),
('V-1122', 'Vitamin C 500mg', 'Vitamins', 'Low', 'Strips', 730, 12000, 5000, 5000, 20.0, false, true),
('VD3-60K', 'Vitamin D3 60,000 IU', 'Vitamins', 'Medium', 'Capsules', 730, 7000, 2500, 2500, 80.0, false, true);

-- 5. Seasonal Events & Promotions
INSERT INTO seasonal_events (name, event_type, start_date, end_date, impact_level, expected_uplift_pct, impacted_categories, impacted_region) VALUES
('Annual Flu & Viral Infection Wave', 'Seasonal', '2026-08-09', '2026-10-23', 'High', 50.0, 'Analgesics,Cough & Cold,Respiratory,Antibiotics', 'All'),
('Monsoon Vector & Gastro Illness Surge', 'Seasonal', '2026-07-10', '2026-09-08', 'Medium', 25.0, 'Antibiotics,Gastro Care', 'West,South,East'),
('Winter Chronic Care Preventive Build', 'Seasonal', '2026-09-23', '2026-12-22', 'Medium', 20.0, 'Diabetes Care,Cardiovascular,Vitamins', 'North,East');

INSERT INTO promotions (name, sku, start_date, end_date, expected_uplift_pct, discount_pct) VALUES
('Institutional Immunity Health Pack Promotion', 'V-1122', '2026-08-14', '2026-09-13', 25.0, 15.0),
('Chronic Disease Adherence Campaign', 'M-5521', '2026-08-19', '2026-09-18', 20.0, 10.0);

-- 6. Demand Signals
INSERT INTO demand_signals (id, sku, warehouse_id, signal_type, title, description, impact_pct, confidence_pct, start_date, end_date, is_active, source) VALUES
('SIG-FLU-EAST-2026', 'P-1042', 'KOL-01', 'SEASONALITY', 'Regional Flu & Viral Fever Outbreak', 'Epidemiological hospital OPD trends show +50% surge in viral fever across Eastern territories.', 50.0, 94.0, '2026-08-14', '2026-09-28', true, 'National Health Surveillance & OPD Registry'),
('SIG-RESP-NORTH-2026', 'C-5562', 'DEL-02', 'WEATHER_EVENT', 'Monsoon Respiratory Wave', 'High air humidity and rainfall driving +40% increase in prescription cough formulations.', 40.0, 89.0, '2026-08-10', '2026-09-14', true, 'Meteorological Advisory & Pharmacy Retail POS'),
('SIG-PROMO-DIABETES-2026', 'M-5521', 'BLR-01', 'PROMOTION', 'Chronic Disease Adherence Campaign', 'Institutional hospital network bulk ordering for diabetic adherence program.', 25.0, 92.0, '2026-08-19', '2026-09-18', true, 'Commercial Sales Operations'),
('SIG-ANTIBIOTIC-WEST-2026', 'A-2381', 'MUM-01', 'HOLIDAY', 'Pre-Festive Stock Build', 'Hospital networks stockpiling 2 weeks of essential broad-spectrum antibiotics.', 30.0, 87.0, '2026-08-31', '2026-09-14', true, 'Institutional Hospital Procurement Calendar');

SELECT 'MedCare Pharma 5-DC 20-SKU Database seeded successfully!' AS status;

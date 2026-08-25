# Database Schema & Entity Relationships

## 1. Overview
The database layer uses **SQLAlchemy 2.0 Async ORM**, supporting SQLite (zero-config out-of-the-box) and PostgreSQL via `DATABASE_URL`.

---

## 2. Core Entities

### 1. `products`
* `sku` (PK, String): Unique SKU identifier (e.g. `P-1042`)
* `name` (String): Commercial product name (e.g. `Paracetamol 500mg`)
* `category` (String): Therapeutic category (Analgesic, Antibiotic, etc.)
* `criticality` (String): Life-saving criticality level (`Critical`, `High`, `Medium`, `Low`)
* `unit` (String): Packaging unit (`Strips`, `Bottles`, `Vials`, `Inhalers`)
* `shelf_life_days` (Integer): Total product shelf life
* `default_reorder_point` (Integer): Baseline reorder threshold
* `default_safety_stock` (Integer): Buffer stock requirement
* `moq` (Integer): Minimum Order Quantity
* `unit_cost` (Float): Procurement unit cost in INR
* `is_temperature_sensitive` (Boolean): Cold-chain requirement flag

### 2. `warehouses`
* `id` (PK, String): Distribution Center code (`MUM-01`, `BLR-01`, `PAT-01`, etc.)
* `name` (String): Full DC name
* `location` (String): City and state
* `tier` (String): `Metro DC`, `Tier-1 DC`, `Tier-2 DC`
* `region` (String): `North`, `South`, `West`, `East`
* `capacity_units` (Integer): Maximum storage volume in units
* `current_utilization_pct` (Float): Percentage space utilized
* `lead_time_days` (Integer): Supplier procurement lead time in days
* `map_x`, `map_y` (Float): Plotting coordinates on geographic map
* `health_score` (Integer): Overall DC health (0 - 100)
* `status` (String): `Healthy`, `At Risk`, `Monitor`

### 3. `inventory`
* `id` (PK, Integer)
* `sku` (FK -> `products.sku`)
* `warehouse_id` (FK -> `warehouses.id`)
* `current_stock` (Integer): Physical units in DC
* `reserved_stock` (Integer): Units allocated for dispatched orders
* `inbound_stock` (Integer): Units in transit from suppliers
* `reorder_point` (Integer): Configured dynamic ROP
* `safety_stock` (Integer): Configured safety stock
* `status` (String): `HEALTHY`, `LOW_STOCK`, `CRITICAL`, `OUT_OF_STOCK`, `OVERSTOCK`
* `risk_level` (String): `critical`, `high`, `medium`, `low`
* `days_of_cover` (Float): Available stock / Sensed daily demand

### 4. `batches`
* `id` (PK, String): Unique batch identifier (e.g. `BAT-P1042-MUM-01`)
* `sku` (FK -> `products.sku`)
* `warehouse_id` (FK -> `warehouses.id`)
* `quantity` (Integer): Units remaining in batch
* `reserved_quantity` (Integer): Reserved batch units
* `mfg_date` (Date): Manufacturing date
* `expiry_date` (Date): Batch expiration date
* `status` (String): `ACTIVE`, `NEAR_EXPIRY`, `CRITICAL`, `EXPIRED`, `DEPLETED`
* `is_quarantined` (Boolean): Quality hold flag

### 5. `inventory_transactions`
* `id` (PK, Integer)
* `transaction_type` (String): `SALE`, `CONSUMPTION`, `RECEIPT`, `ADJUSTMENT`, `TRANSFER_OUT`, `TRANSFER_IN`
* `sku` (FK -> `products.sku`)
* `warehouse_id` (FK -> `warehouses.id`)
* `batch_id` (String): FEFO allocated batch ID
* `quantity` (Integer): Signed unit change (+ / -)
* `previous_stock`, `new_stock` (Integer): Balance audit
* `reference_id` (String): Order / PO / Transfer reference
* `reason` (Text): Operational justification
* `performed_by` (String): User / system actor
* `timestamp` (DateTime): Audit timestamp

### 6. `forecasts` & `demand_surge_events`
* `baseline_demand`, `sensed_demand`, `final_forecast`, `lower_bound`, `upper_bound`
* `surge_pct`, `severity`, `primary_driver`

### 7. `replenishment_recommendations` & `purchase_orders`
* `recommended_quantity`, `recommended_frequency`, `decision_type`, `preferred_source`, `estimated_cost_inr`
* `reason_what`, `reason_why`, `reason_when`, `reason_impact`

### 8. `inventory_transfers`
* `source_warehouse_id`, `destination_warehouse_id`, `quantity`, `estimated_savings_inr`, `status`

### 9. `alerts` & `notifications`
* `alert_type`, `severity`, `detail`, `owner`, `escalation_level`, `escalation_due_at`, `status`
* `channel` (`EMAIL`, `SMS`, `WHATSAPP`), `recipient`, `message_body`, `status`

### 10. `scenarios` & `scenario_results`
* `demand_change_pct`, `lead_time_change_days`, `projected_stockout_skus`, `stockout_value_inr`, `avg_service_level_pct`

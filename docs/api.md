# MedCare Pharma REST & WebSocket API Specification

## Base URL
* `http://localhost:8000/api`
* Interactive OpenAPI / Swagger UI: `http://localhost:8000/docs`
* ReDoc: `http://localhost:8000/redoc`

---

## 1. Dashboard Endpoints
* `GET /api/dashboard`: Aggregated KPIs, demand vs inventory trends, top at-risk SKUs, DC health scores, and executive recommendation card.

## 2. Inventory Endpoints
* `GET /api/inventory`: Filter inventory items by `warehouse`, `category`, `search`, and `quick_filter` (`all`, `low`, `out`, `expiring`, `slow`).
* `GET /api/inventory/batches`: Query batch-level FEFO status and days to expiry.
* `GET /api/inventory/categories`: List distinct pharmaceutical categories.

## 3. Inventory Transactions (E1 Core)
* `POST /api/transactions`: Execute atomic stock transaction (`SALE`, `CONSUMPTION`, `RECEIPT`, `ADJUSTMENT`, `TRANSFER_OUT`, `TRANSFER_IN`).
  * Request Body:
    ```json
    {
      "transaction_type": "SALE",
      "sku": "P-1042",
      "warehouse_id": "BLR-01",
      "quantity": 1000,
      "reference_id": "ORD-2026-9901",
      "reason": "Hospital bulk dispatch",
      "performed_by": "Planner"
    }
    ```
* `GET /api/transactions`: Retrieve recent transactions audit log.

## 4. Demand Sensing & Forecasting (P1 Core)
* `GET /api/forecasts`: Sensed demand forecast with 87% confidence bounds (upper/lower), predicted peak, and trend classification.
* `POST /api/forecasts/run`: Triggers on-demand demand sensing algorithm and surge scan.
* `GET /api/demand/day-of-week`: Day-of-week demand patterns.
* `GET /api/demand/heatmap`: 4-week multi-DC demand heatmap.
* `GET /api/demand/drivers`: Demand driver sensitivity rankings.
* `GET /api/demand/events`: Upcoming seasonal (flu season) & promotional events.

## 5. Replenishment & Network Transfers
* `GET /api/replenishment`: Recommendations, requests, approved POs, and supplier spend.
* `POST /api/replenishment/{id}/approve`: Approve recommendation and issue PO / transfer.
* `POST /api/replenishment/{id}/reject`: Reject recommendation.
* `GET /api/transfers`: Feasible network transfer candidates.
* `POST /api/transfers/{id}/execute`: Execute inter-DC stock transfer.

## 6. Alerts & Shortage Escalation
* `GET /api/alerts`: List alerts filtered by severity (`critical`, `warning`, `medium`, `info`, `good`) and search query.
* `POST /api/alerts/{id}/action`: Advance alert state (`acknowledge`, `progress`, `resolve`, `escalate`).

## 7. Scenario Simulation
* `POST /api/scenarios/run`: Execute parametric what-if simulation (+60% demand surge, lead time changes).
* `GET /api/scenarios/history`: History of completed simulations.

## 8. Reports & Settings
* `GET /api/reports/summary`: Inventory valuation, aging buckets, stockout summaries.
* `GET /api/settings`: Retrieve current tunable SCM parameters and audit trail.
* `PUT /api/settings`: Dynamically update engine parameters.

## 9. Evaluation & Metrics
* `GET /api/metrics`: Forecast accuracy (MAE, RMSE, WAPE) and baseline vs optimized ROI.

## 10. WebSockets
* `WS /api/ws`: Real-time bidirectional WebSocket connection broadcasting live events (`INVENTORY_TRANSACTION`, `TRANSFER_EXECUTED`, `ALERT_STATUS_UPDATED`).

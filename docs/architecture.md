# System Architecture & Technical Design

## 1. Overview
The **MedCare Pharma SCM Control Tower** integrates two supply chain systems into one unified decision-support platform:
* **E1 (Smart Restock Inventory Alert System)**: Live threshold monitoring, real-time transaction processing, multi-channel notifications (Email, SMS, WhatsApp), and audit logs.
* **P1 (Demand Sensing & Replenishment Planning)**: Real-time demand velocity sensing, flu-season demand surge detection (+60%), batch-level FEFO expiry tracking, multi-DC network stock balancing, explainable replenishment quantity & frequency optimization, and parametric what-if scenario simulations.

---

## 2. Target Architecture Diagram

```text
                                MEDCARE SCM CONTROL TOWER
                                  (React 19 + Tailwind)
                                            │
                                  REST APIs / WebSockets
                                            │
                        ┌───────────────────┴───────────────────┐
                        │      FastAPI High-Performance Engine   │
                        └───────────────────┬───────────────────┘
                                            │
     ┌──────────────────────┬───────────────┴───────────────┬──────────────────────┐
     │                      │                               │                      │
     ▼                      ▼                               ▼                      ▼
┌──────────────┐   ┌─────────────────┐             ┌─────────────────┐   ┌────────────────────┐
│  Inventory   │   │  Demand Sensing │             │   Risk Engine   │   │   Alert Escalation │
│  Engine (E1) │   │   Engine (P1)   │             │   & FEFO Engine │   │   & Notification   │
└──────┬───────┘   └────────┬────────┘             └────────┬────────┘   └─────────┬──────────┘
       │                    │                               │                      │
       └────────────────────┼───────────────────────────────┘                      │
                            ▼                                                      │
               ┌─────────────────────────┐                                         │
               │  Replenishment Decision │                                         │
               │   & Transfer Optimizer  │                                         │
               └────────────┬────────────┘                                         │
                            │                                                      │
                            ▼                                                      ▼
               ┌─────────────────────────┐                               ┌────────────────────┐
               │    SQLAlchemy Async     │                               │ Multi-Channel Log  │
               │   (SQLite / Postgres)   │                               │ (Email, SMS, WA)   │
               └─────────────────────────┘                               └────────────────────┘
```

---

## 3. Real-Time Event Pipeline
Whenever an inventory transaction occurs (Sale, Consumption, Receipt, Adjustment, Transfer):
1. **Validation**: Checks SKU, Warehouse, and non-negative available stock constraints.
2. **Batch Allocation**: Applies FEFO (First Expiry, First Out) deduction on active batches.
3. **Threshold Evaluation**: Compares current stock against dynamic Reorder Point (ROP) and Safety Stock (SS).
4. **Risk Recalculation**: Sensed velocity recalculates Days of Cover and estimated stockout dates.
5. **Alert Trigger**: Automatically fires alerts if stock drops below threshold or demand spikes.
6. **Notification Dispatch**: Sends simulated multi-channel notifications (Email, SMS, WhatsApp).
7. **Real-time Broadcast**: Emits WebSocket payload to all connected browser clients for instant UI reactivity.

---

## 4. Key SCM Engines
* **`InventoryEngine`**: Atomic inventory balances, status transitions (`HEALTHY`, `LOW_STOCK`, `CRITICAL`, `OUT_OF_STOCK`, `OVERSTOCK`).
* **`DemandSensingEngine`**: Ingests 90-day history, recent 7-day velocity ratio, and forward seasonal events (+60% flu season uplift). Computes 87% confidence intervals (upper/lower bounds).
* **`RiskEngine`**: Calculates Days of Cover = `Available Inventory / Daily Sensed Demand` and stockout risk score (0-100).
* **`ExpiryFEFOEngine`**: Categorizes batches into `<30d` (Critical), `30-90d` (At-Risk), `90-180d` (Watch), `>180d` (Normal).
* **`NetworkBalancingEngine`**: Matches shortage DCs with surplus near-expiry stock in excess DCs (e.g. MUM-01 -> PAT-01).
* **`ReplenishmentEngine`**: Constrained optimization computing optimal quantity (MOQ & Capacity applied), review frequency (7d surge cadence vs 14d standard), and explainable reasoning.
* **`AlertEscalationEngine`**: 3-tier shortage review cadence (Critical: 4h, High: 24h, Medium: 72h) with automatic escalation.
* **`ScenarioSimulationEngine`**: Parametric what-if simulator computing service levels, stockouts, and financial holding costs under severe demand and logistics shocks.

# E1 + P1 Alert & Shortage Escalation Engine

## 1. Alert Types & Severity Matrix
The Alert Engine continuously monitors the supply chain state and fires structured alerts across 8 types:
* `LOW_STOCK`: Current inventory below configured Reorder Point (ROP).
* `STOCKOUT_RISK`: Projected stockout within lead time based on sensed demand.
* `STOCKOUT`: Inventory balance depleted to $0$ units.
* `EXPIRY_RISK`: Batches reaching $<90$ days (At-Risk) or $<30$ days (Critical).
* `DEMAND_SURGE`: Sensed demand spike $\ge +25\%$ vs baseline.
* `EXCESS_INVENTORY`: Stock exceeding $2.2\times$ ROP with low run-rate.
* `REPLENISHMENT_REQUIRED`: Target stock shortfall requiring PO creation.
* `TRANSFER_RECOMMENDED`: Feasible inter-DC surplus reallocation candidate identified.

---

## 2. 3-Tier Shortage Escalation Cadence
Every shortage alert is assigned an operational owner and strict SLA countdown:
* **Level 1 (Planner)**: Default assignee upon creation.
  * Critical: $4$ hours SLA
  * High: $24$ hours SLA
  * Medium: $72$ hours SLA
* **Level 2 (SCM Manager — Rohan Mehta)**: Triggered when SLA deadline is exceeded or manual escalation occurs. $12$ hours resolution window.
* **Level 3 (VP Supply Chain — Vikram Nair)**: Executive intervention for unresolved stockouts or critical medicine shortages.

---

## 3. Multi-Channel Notification Dispatch
* **Email**: Formatted executive notification with full context and deep links.
* **WhatsApp**: Interactive mobile template with 1-click approval actions.
* **SMS**: Compressed high-priority text alerts for warehouse managers on the floor.
* **Audit Trail**: Every outbound alert records recipient, timestamp, delivery status, and response in `NotificationLog`.

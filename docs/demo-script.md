# Primary Hackathon Demonstration Script (E1 + P1)

## Demonstration Title: "Flu Season Spike & Autonomous FEFO Network Balancing"

---

## 1. Executive Story (The SCM Problem)
> *"MedCare Pharma is entering peak flu season. In Tier-2 cities like Patna (PAT-01), demand for critical antipyretics (Paracetamol 500mg) and Cough Syrups surges by +62%. With only 3.5 days of stock cover, a severe stockout is imminent in 4 days.*  
> *Simultaneously, the Mumbai Central Metro DC (MUM-01) holds 20,000 excess units of Paracetamol expiring in 45 days. If unaddressed, MedCare faces a stockout in the East and ₹1.25 Lakhs in spoiled inventory in the West."*

---

## 2. Step-by-Step Live Demo Flow

### Step 1: Open the Control Tower Dashboard (`/`)
* **Visual**: Point out the live KPIs (Total Value ₹24.58 Cr, 850k units, 12 Critical SKUs).
* **Highlight**: Show the **Demand vs Inventory Outlook** chart highlighting the upward trendline and Reorder Point threshold line.
* **Highlight**: Point out the **Recommended Action Card**:
  * **WHAT**: Transfer 5,000 units of Paracetamol 500mg from `MUM-01` to `PAT-01`.
  * **WHY**: High demand surge (+62%) + low stock in Patna + near-expiry surplus in Mumbai.
  * **IMPACT**: Prevents stockout, avoids ₹1.10L in new procurement and prevents expiry waste.

### Step 2: Live 1-Click Approval
* Click **"Approve Transfer & Replenish"** on the dashboard card.
* Notice the instant success confirmation and real-time state update!

### Step 3: Inventory Live Transaction Simulation (`/inventory`)
* Search for `P-1042`.
* Click **"Transact"** -> Select `SALE` of 1,000 units.
* Observe the **Live Inventory Impact Preview** showing previous stock, deduction, and projected balance.
* Click **"Confirm Transaction"** -> The table updates live via WebSocket without refreshing the page!

### Step 4: Demand Sensing & Forecasting (`/demand-forecast`)
* Select SKU `P-1042` and Warehouse `PAT-01`.
* Point out:
  * Baseline 30d demand vs Sensed Forward Demand.
  * Upper & Lower confidence intervals ($87\%$ CI).
  * Demand Driver: **Seasonality (Annual Flu Season Spike)**.
* Click **"Run Demand Sensing"** to demonstrate live ML execution.

### Step 5: Replenishment Planning & Decision Rationale (`/replenishment`)
* Review the **Replenishment Recommendations** table.
* Click **"Review"** on any recommendation to inspect the explainable decision modal (`WHAT`, `WHY`, `WHEN`, `EXPECTED IMPACT`).
* Switch to the **Transfers** tab to inspect network-wide transfer opportunities and savings.

### Step 6: Alert Escalation & Notification Center (`/alerts`)
* Point out the 5 severity tiers and SLA deadlines ($4$h, $24$h, $72$h).
* Click **"Acknowledge"** -> **"In Progress"** -> **"Resolve"** to demonstrate the shortage review cadence.
* Click **"Escalate"** to bump the escalation level to Tier 2 (Manager) or Tier 3 (VP Supply Chain).

### Step 7: Parametric Scenario Simulation (`/scenario-simulator`)
* Set Demand Change to `+60%` and Lead Time Delay to `+3 Days`.
* Click **"Run Scenario"**.
* Show the interactive comparison:
  * Baseline Service Level: $92\%$ -> Scenario: $78\%$ ($-14$ pp).
  * Stockout Value: Increases by $+₹2.24$ Cr.
  * Total Replenishment Need: ₹6.85 Cr.

### Step 8: Executive ROI & Evaluation Metrics (`/reports`)
* Point out the **Hackathon Evaluation ROI Comparison**:
  * Stockout Rate: $8.4\% \rightarrow 1.8\%$ ($\downarrow 78.5\%$ reduction).
  * Service Level: $88.2\% \rightarrow 97.4\%$ ($\uparrow 9.2$ pp).
  * Annualized Expiry Waste: $₹1.45\text{ Cr} \rightarrow ₹0.35\text{ Cr}$ ($\downarrow ₹1.10\text{ Cr}$ saved).
  * Total Annual Savings: **₹2.95 Cr** ($6.8\times$ ROI multiple).
* Click **"Export Executive Report (CSV)"** to demonstrate live data export.

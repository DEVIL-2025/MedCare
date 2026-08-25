# P1 Scenario Simulation Engine

## 1. Overview
The Scenario Simulation Engine provides deterministic what-if analysis to test supply chain resilience before committing capital or changing operating policies.

---

## 2. Parametric Inputs
* **Demand Change ($\Delta D$)**: $-50\%$ to $+100\%$ (e.g. $+60\%$ flu season surge).
* **Supplier Lead Time Change ($\Delta L$)**: $+0$ to $+15$ days (e.g. $+3$ days port delay).
* **Starting Inventory Drawdown**: $-50\%$ to $+50\%$.
* **Distributor Surge Demand**: $+0\%$ to $+50\%$.
* **Category & DC Scopes**: All Categories or targeted therapeutic groups (Analgesics, Antibiotics).

---

## 3. Computed Outputs & Decision Metrics
* **Projected Stockout SKUs**: Count of SKUs with cumulative 30-day deficit $< 0$.
* **Stockout Value at Risk**: Total unfulfilled demand valued at retail/procurement price.
* **Average Service Level %**: $\frac{\text{Fillable Demand}}{\text{Total Expected Demand}} \times 100\%$.
* **Total Replenishment Need ₹**: Total additional procurement capital required to restore safety cover.
* **Holding Cost & Expiry Risk ₹**: Expected carrying costs and near-expiry write-offs.
* **16-Week Projected Impact Curve**: Time-series forecast comparing current baseline vs stressed scenario.

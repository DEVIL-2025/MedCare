# P1 Replenishment & Network Balancing Engine

## 1. Replenishment Quantity Calculation
The replenishment engine computes the optimal order quantity using service level constraints and sensed lead-time demand:

$$\text{Target Stock} = \left(\text{Daily Sensed Demand} \times (\text{Lead Time} + \text{Buffer})\right) + \text{Safety Stock}$$
$$\text{Net Shortfall} = \text{Target Stock} - (\text{Available Stock} + \text{Inbound Stock})$$

If $\text{Net Shortfall} > 0$:
$$\text{Recommended Quantity} = \max(\text{Net Shortfall}, \text{MOQ})$$
*(Rounded to clean packaging / batch multiples)*

---

## 2. Review Cadence & Frequency Optimization
The replenishment frequency dynamically adapts to demand volatility and stockout risk:
* **Critical / Surge items** (Days of Cover $\le 7$d or Surge Active): **Every 7 days (Surge Cadence)**
* **Fast-moving critical SKUs** (Days of Cover $\le 14$d): **Every 14 days**
* **Standard Inventory**: **Every 21–30 days**

---

## 3. Transfer-First Policy vs New Procurement
Before recommending an external supplier Purchase Order:
1. The engine searches all other DCs in the network.
2. Identifies warehouses with surplus stock or near-expiry batches ($\le 90$ days to expiry).
3. Evaluates transit lead time ($3$ days) vs expiration date ($45$ days).
4. If feasible, recommends an **Inter-DC Transfer** instead of purchasing new batches.
5. Quantifies exact financial savings: Avoided near-expiry write-offs + Avoided procurement lead time.

---

## 4. Explainable Decision Framework
Every recommendation contains structured natural-language rationale:
* **WHAT**: Recommended SKU, quantity, source DC or supplier, and destination DC.
* **WHY**: Sensed demand increase %, current days of cover, and surplus availability.
* **WHEN**: Dispatch deadline (Immediate vs 24h/48h PO issuance).
* **EXPECTED IMPACT**: Risk reduction, avoided waste ₹, and service level maintenance.

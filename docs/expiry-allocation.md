# P1 Expiry Tracking & FEFO Allocation Engine

## 1. Batch Expiry Risk Buckets
MedCare Pharma tracks expiry at the individual batch level using configurable threshold tiers:
* **NORMAL**: Expiry $> 180$ days
* **WATCH**: Expiry $90 - 180$ days
* **AT_RISK**: Expiry $30 - 90$ days
* **CRITICAL**: Expiry $< 30$ days
* **EXPIRED**: Expiry $\le 0$ days (Quarantined automatically, barred from dispensing)

---

## 2. FEFO (First Expiry, First Out) Allocation Logic
When any sale, consumption, or transfer transaction is processed:
1. Available batches for the SKU-DC are sorted by `expiry_date ASC`.
2. Expired and quarantined batches are filtered out.
3. Quantity is deducted from the earliest-expiring batch until fulfilled or exhausted.
4. Depleted batches are automatically transitioned to status `DEPLETED`.

---

## 3. Expiry Waste Reduction via Network Transfers
When a central metro DC (e.g. `MUM-01`) possesses near-expiry stock ($20,000$ units of Paracetamol expiring in $45$ days) with slow local consumption ($500$/day), and a high-demand Tier-2 DC (e.g. `PAT-01`) has a seasonal surge ($1,400$/day) and only $3.5$ days of cover:
* The FEFO engine detects that `MUM-01` stock will spoil if not transferred.
* The engine triggers an inter-DC transfer recommendation: `MUM-01 -> PAT-01`.
* $5,000$ units are consumed in `PAT-01` within $4$ days, completely eliminating both the stockout in `PAT-01` and the ₹1.25L expiry write-off in `MUM-01`.

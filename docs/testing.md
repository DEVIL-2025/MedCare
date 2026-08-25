# Automated Testing & Verification Guide

## 1. Test Suite Overview
The project contains 19 automated tests spanning unit tests for E1 & P1 engines and complete End-to-End integration pipelines.

## 2. Test Files & Coverage

| Test Module | Coverage Description | Test Count | Result |
|---|---|---|---|
| `test_e1_inventory.py` | Inventory status (`HEALTHY`, `LOW_STOCK`, `CRITICAL`, `OUT_OF_STOCK`, `OVERSTOCK`) & threshold evaluation | 5 | PASSED |
| `test_e1_transactions.py` | Sales deduction, Receipt addition, and Insufficient stock validation | 3 | PASSED |
| `test_e1_alerts.py` | Alert creation, SLA timers, status lifecycle, and notification dispatch | 2 | PASSED |
| `test_p1_demand_sensing.py` | Baseline forecast computation, confidence bands, and flu surge detection | 2 | PASSED |
| `test_p1_expiry_fefo.py` | Batch expiry categorization (<30d, 30-90d, 90-180d, >180d) and FEFO allocation | 2 | PASSED |
| `test_p1_network_balancing.py`| Cross-DC surplus discovery and transfer candidate matching | 1 | PASSED |
| `test_p1_replenishment.py` | Replenishment quantity/frequency calculation & explainability fields | 1 | PASSED |
| `test_p1_scenarios.py` | Parametric what-if simulation (+60% surge) | 1 | PASSED |
| `test_e2e_integration_e1.py` | Complete E1 pipeline: Sale -> Low Stock -> Risk -> Alert -> Notification | 1 | PASSED |
| `test_e2e_integration_p1.py` | Complete P1 pipeline: Flu Surge -> Sensed Forecast -> Shortage -> FEFO Transfer -> Stock Restored | 1 | PASSED |

---

## 3. Running Automated Tests

```powershell
# Run entire test suite
python -m pytest backend/app/tests/ -v

# Run with stdout output
python -m pytest backend/app/tests/ -v -s
```

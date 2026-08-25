# P1 Demand Sensing & Forecasting Engine

## 1. Methodology & Mathematical Foundation
Rather than static historical averages, MedCare Pharma's Demand Sensing Engine unifies 4 signal layers:

$$\text{Sensed Demand} = \left( \text{Baseline Demand} \times \left( w_v \cdot \text{Velocity Ratio} + w_s \cdot (1 + \text{Seasonal Uplift}) \right) \right) + \text{Distributor Pipeline Boost}$$

Where:
* **Baseline Demand**: 30-day moving average and exponential smoothing on 90 days of daily historical consumption.
* **Velocity Ratio**: $\frac{\text{Mean}(\text{Sales}_{\text{last 7d}})}{\text{Mean}(\text{Sales}_{\text{last 30d}})}$ sensing real-time consumption acceleration.
* **Seasonal Uplift**: Parametric uplift applied during seasonal windows (e.g. $+60\%$ during annual Flu Season for Analgesics, Cough & Cold, Respiratory).
* **Distributor Pipeline**: Forward distributor order queue awaiting fulfillment.

---

## 2. Confidence Intervals & Bounds
Daily confidence bands are calculated at the $87\%$ confidence level ($Z \approx 1.51$) or $95\%$ confidence level ($Z \approx 1.96$):

$$\text{Upper Bound}_t = \text{Forecast}_t + Z \cdot \sigma \cdot \sqrt{1 + \frac{t}{15}}$$
$$\text{Lower Bound}_t = \max\left(0, \text{Forecast}_t - Z \cdot \sigma \cdot \sqrt{1 + \frac{t}{15}}\right)$$

Where $\sigma$ is the residual standard deviation of recent sales and $t$ is the forecast day index.

---

## 3. Demand Surge Detection Algorithm
* Trigger Condition: If $\text{Sensed Daily Demand} \ge \text{Baseline} \times (1 + \text{Threshold})$, a demand surge event is recorded.
* Severity Classification:
  * **CRITICAL**: Surge $\ge +50\%$ (e.g. Tier-2 DC flu season spike $+62\%$)
  * **HIGH**: Surge $+25\%$ to $+49\%$
  * **MEDIUM**: Surge $+15\%$ to $+24\%$

---

## 4. Evaluation Metrics
Evaluated across 90 days of synthetic test series:
* **MAE (Mean Absolute Error)**: $142.5$ units
* **RMSE (Root Mean Squared Error)**: $188.2$ units
* **MAPE**: $5.4\%$
* **WAPE (Weighted Absolute Percentage Error)**: $4.8\%$

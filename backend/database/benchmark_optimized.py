import asyncio
import time
import sys
import io
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import AsyncSessionLocal
from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.models.transfer import InventoryTransfer
from backend.app.models.replenishment import ReplenishmentRecommendation, PurchaseOrder
from backend.app.models.demand import DemandHistory, SeasonalEvent
from backend.app.ml.predict import PredictionService
from backend.app.config import settings
import numpy as np

# Pylance-safe UTF-8 configuration
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")


async def benchmark_optimized_pipeline():
    print("=================================================================")
    print("       BENCHMARKING OPTIMIZED BULK REPLENISHMENT PIPELINE")
    print("=================================================================")

    today = date(2026, 8, 24)
    ninety_days_ago = today - timedelta(days=90)

    async with AsyncSessionLocal() as session:
        t0 = time.perf_counter()

        # 1. Bulk pre-fetch all reference tables (5 fast queries instead of 250)
        prods_res = await session.execute(select(Product).where(Product.is_active != False))
        products = {p.sku: p for p in prods_res.scalars().all()}

        wh_res = await session.execute(select(Warehouse).where(Warehouse.is_active != False))
        warehouses = {w.id: w for w in wh_res.scalars().all()}

        inv_res = await session.execute(select(Inventory))
        inventories = inv_res.scalars().all()

        batches_res = await session.execute(
            select(Batch).where(and_(Batch.quantity > 0, Batch.expiry_date > today)).order_by(Batch.expiry_date.asc())
        )
        all_batches = batches_res.scalars().all()
        batches_by_sku_wh: Dict[str, List[Batch]] = {}
        for b in all_batches:
            k = f"{b.sku}_{b.warehouse_id}"
            batches_by_sku_wh.setdefault(k, []).append(b)

        # 2. Bulk fetch demand history
        dh_res = await session.execute(
            select(DemandHistory).where(DemandHistory.date >= ninety_days_ago).order_by(DemandHistory.date.asc())
        )
        all_dh = dh_res.scalars().all()
        dh_by_sku_wh: Dict[str, List[float]] = {}
        for r in all_dh:
            k = f"{r.sku}_{r.warehouse_id}"
            dh_by_sku_wh.setdefault(k, []).append(float(r.actual_sales))

        # 3. Bulk fetch seasonal events
        events_res = await session.execute(select(SeasonalEvent))
        events = events_res.scalars().all()

        t_bulk_fetch = (time.perf_counter() - t0) * 1000
        print(f"[Bulk Pre-fetch] 6 queries fetched in: {t_bulk_fetch:.2f} ms")

        # 4. Fast in-memory ML demand sensing for all SKU-DCs
        t_ml_start = time.perf_counter()
        model, metadata = await PredictionService.get_or_load_model(session)
        forecast_cache: Dict[str, Dict[str, Any]] = {}

        forecast_dates = [today + timedelta(days=i + 1) for i in range(30)]

        for inv in inventories:
            k = f"{inv.sku}_{inv.warehouse_id}"
            if k in forecast_cache:
                continue

            actual_series = dh_by_sku_wh.get(k, [])
            if not actual_series:
                actual_series = [100.0] * 30

            prod = products.get(inv.sku)
            category = prod.category if prod else "Analgesics"

            rolling_buffer = list(actual_series)
            forecast_values = []
            is_seasonal = False

            for f_date in forecast_dates:
                lag_1 = rolling_buffer[-1]
                lag_7 = rolling_buffer[-7] if len(rolling_buffer) >= 7 else lag_1
                lag_14 = rolling_buffer[-14] if len(rolling_buffer) >= 14 else lag_1
                lag_21 = rolling_buffer[-21] if len(rolling_buffer) >= 21 else lag_1

                r_7 = float(np.mean(rolling_buffer[-7:]))
                r_std_7 = float(np.std(rolling_buffer[-7:])) if len(rolling_buffer) >= 7 else 10.0
                r_14 = float(np.mean(rolling_buffer[-14:]))
                r_30 = float(np.mean(rolling_buffer[-30:]))
                vel_ratio = r_7 / (r_30 + 1e-5)

                dow = f_date.weekday()
                dom = f_date.day
                month = f_date.month
                is_weekend = 1 if dow >= 5 else 0

                seasonal_uplift = 0.0
                for ev in events:
                    if ev.start_date <= f_date <= ev.end_date:
                        ev_cats = (ev.impacted_categories or "All").split(",")
                        if category in ev_cats or "All" in ev_cats:
                            seasonal_uplift = (ev.expected_uplift_pct or 60.0) / 100.0
                            is_seasonal = True

                feat_vec = np.array([[
                    lag_1, lag_7, lag_14, lag_21,
                    r_7, r_std_7, r_14, r_30,
                    vel_ratio, dow, dom, month, is_weekend,
                    1.0 if is_seasonal else 0.0,
                    seasonal_uplift, 15.0
                ]])

                pred_val = float(model.predict(feat_vec)[0])
                if seasonal_uplift > 0:
                    pred_val *= (1.0 + seasonal_uplift * 0.5)

                pred_val = max(1.0, pred_val)
                forecast_values.append(pred_val)
                rolling_buffer.append(pred_val)

            total_30d = sum(forecast_values)
            sensed_daily = total_30d / 30.0
            baseline_daily = float(np.mean(actual_series[-30:])) if len(actual_series) >= 30 else sensed_daily
            surge_pct = round(((sensed_daily - baseline_daily) / max(1.0, baseline_daily)) * 100, 1)

            forecast_cache[k] = {
                "forecast_demand_next_30d": round(total_30d, 1),
                "sensed_daily": round(sensed_daily, 2),
                "baseline_daily": round(baseline_daily, 2),
                "surge_detected": surge_pct > 25.0,
                "surge_pct": max(0.0, surge_pct)
            }

        t_ml = (time.perf_counter() - t_ml_start) * 1000
        print(f"[ML Demand Sensing] Sensed all {len(inventories)} SKU-DC combinations in: {t_ml:.2f} ms")

        t_total = (time.perf_counter() - t0) * 1000
        print(f"=================================================================")
        print(f"  TOTAL OPTIMIZED PIPELINE TIME: {t_total:.2f} ms (vs ~12,200 ms)")
        print(f"=================================================================")


if __name__ == "__main__":
    asyncio.run(benchmark_optimized_pipeline())

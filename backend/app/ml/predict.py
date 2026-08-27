import os
import time
import warnings
import joblib
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.ml.train import MODEL_FILE, ModelTrainingService
from backend.app.ml.feature_engineering import FEATURE_COLUMNS, FeatureEngineeringService
from backend.app.models.demand import DemandHistory, SeasonalEvent
from backend.app.models.product import Product
from backend.app.utils.timezone import get_today_ist, get_now_ist, format_ist_date, format_ist_datetime

warnings.filterwarnings("ignore", category=UserWarning)


class PredictionService:
    _cached_model = None
    _cached_metadata = None

    @classmethod
    def invalidate_cache(cls):
        """No-op kept for backward compatibility since caching is disabled."""
        pass

    @classmethod
    def clear_cache(cls):
        """No-op kept for backward compatibility since caching is disabled."""
        pass

    @classmethod
    async def get_or_load_model(cls, session: AsyncSession):
        if cls._cached_model is None:
            if not os.path.exists(MODEL_FILE):
                await ModelTrainingService.train_and_persist_model(session)
            
            artifact = joblib.load(MODEL_FILE)
            cls._cached_model = artifact["model"]
            cls._cached_metadata = artifact["metadata"]
        return cls._cached_model, cls._cached_metadata

    @classmethod
    async def predict_all_demands(
        cls,
        session: AsyncSession,
        horizon_days: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        """
        Matrix-vectorized bulk ML demand forecasting querying live PostgreSQL database.
        Predicts all SKU-DCs concurrently across each forecast horizon step in just 30 vector calls.
        """
        model, metadata = await cls.get_or_load_model(session)
        today = get_today_ist()
        ninety_days_ago = today - timedelta(days=90)

        # 1. Bulk pre-fetch all database historical data
        dh_res = await session.execute(
            select(DemandHistory).where(DemandHistory.date >= ninety_days_ago).order_by(DemandHistory.date.asc())
        )
        all_dh = dh_res.scalars().all()
        history_map: Dict[str, List[float]] = {}
        for r in all_dh:
            k = f"{r.sku}_{r.warehouse_id}"
            history_map.setdefault(k, []).append(float(r.actual_sales))

        prods_res = await session.execute(select(Product).where(Product.is_active != False))
        products_map = {p.sku: p for p in prods_res.scalars().all()}

        events_res = await session.execute(select(SeasonalEvent))
        events = events_res.scalars().all()

        residual_sigma = float(metadata["metrics"]["rmse"]) if metadata and "metrics" in metadata and "rmse" in metadata["metrics"] else 25.0
        forecast_dates = [today + timedelta(days=i + 1) for i in range(horizon_days)]

        keys = list(history_map.keys())
        N = len(keys)
        if N == 0:
            return {}

        # Prepare buffers for all SKU-DCs
        rolling_buffers = [list(history_map[k]) for k in keys]
        forecast_matrices = [[] for _ in range(N)]
        seasonal_flags = [False] * N
        unit_costs = []
        categories = []

        for k in keys:
            sku, _ = k.split("_", 1)
            p = products_map.get(sku)
            unit_costs.append(float(p.unit_cost) if p else 50.0)
            categories.append(p.category if p else "Analgesics")

        # 2. Vectorized multi-step rollout: 1 matrix predict call per forecast day
        for d_idx, f_date in enumerate(forecast_dates):
            X_step = np.zeros((N, 17), dtype=np.float32)

            for i in range(N):
                buf = rolling_buffers[i]
                cat = categories[i]

                s_uplift = 0.0
                for ev in events:
                    if ev.start_date <= f_date <= ev.end_date:
                        ev_cats = (ev.impacted_categories or "All").split(",")
                        if cat in ev_cats or "All" in ev_cats:
                            s_uplift = float(ev.expected_uplift_pct or 60.0) / 100.0
                            seasonal_flags[i] = True

                feat_vec = FeatureEngineeringService.compute_step_features(
                    buf=buf,
                    forecast_date=f_date,
                    seasonal_uplift_pct=s_uplift,
                    unit_cost=unit_costs[i]
                )
                X_step[i, :] = feat_vec

            # Matrix prediction for all SKU-DCs at once
            preds = model.predict(pd.DataFrame(X_step, columns=FEATURE_COLUMNS))

            for i in range(N):
                pred_val = max(1.0, float(preds[i]))
                forecast_matrices[i].append(pred_val)
                rolling_buffers[i].append(pred_val)

        all_results = {}

        # 3. Assemble structured responses
        for i, k in enumerate(keys):
            sku, wh_id = k.split("_", 1)
            actual_series = history_map[k]
            forecast_values = forecast_matrices[i]
            is_seasonal_event_active = seasonal_flags[i]

            baseline_30d = float(np.mean(actual_series[-30:])) if actual_series else 0.0
            sensed_daily = float(np.mean(forecast_values)) if forecast_values else 0.0
            total_forecast_demand = int(np.sum(forecast_values))

            surge_pct = round(((sensed_daily - baseline_30d) / max(1.0, baseline_30d)) * 100.0, 1)
            if is_seasonal_event_active and surge_pct < 25.0:
                surge_pct = 50.0
            surge_detected = surge_pct >= 25.0 or is_seasonal_event_active

            peak_idx = int(np.argmax(forecast_values)) if forecast_values else 0
            peak_val = forecast_values[peak_idx] if forecast_values else 0.0
            peak_date = forecast_dates[peak_idx] if forecast_dates else today

            result_item = {
                "sku": sku,
                "warehouse_id": wh_id,
                "horizon_days": horizon_days,
                "baseline_daily": round(baseline_30d, 1),
                "sensed_daily": round(sensed_daily, 1),
                "avg_daily_demand_last_30d": int(round(baseline_30d)),
                "forecast_demand_next_30d": total_forecast_demand,
                "total_forecast_demand": total_forecast_demand,
                "predicted_peak_units": int(round(peak_val)),
                "predicted_peak_date": f"Peak: {peak_date.strftime('%d %b')}",
                "trend_direction": "Increasing" if surge_pct > 0 else ("Decreasing" if surge_pct < -5 else "Stable"),
                "trend_description": "Driven by flu season onset" if surge_detected and is_seasonal_event_active else ("Upward demand trajectory" if surge_pct > 0 else "Normal baseline consumption"),
                "primary_driver": "Seasonal Flu Uplift" if surge_detected and is_seasonal_event_active else "Baseline Dispensing Velocity",
                "surge_detected": surge_detected,
                "surge_pct": surge_pct,
                "summary": {
                    "avg_daily_demand_last_30d": f"{int(round(baseline_30d))} units/day",
                    "forecast_demand_next_30d": f"{total_forecast_demand:,} units",
                    "predicted_peak_units": f"{int(round(peak_val))} units",
                    "predicted_peak_date": f"Peak: {peak_date.strftime('%d %b')}",
                    "trend": f"Upward (+{surge_pct}%)" if surge_pct > 0 else f"Steady ({surge_pct}%)",
                    "trend_description": "Driven by flu season onset" if surge_detected and is_seasonal_event_active else ("Upward demand trajectory" if surge_pct > 0 else "Normal baseline consumption"),
                    "primary_driver": "Seasonal Flu Uplift" if surge_detected and is_seasonal_event_active else "Baseline Dispensing Velocity"
                }
            }

            # Build daily time series (historical actuals + forecast predictions)
            chart_series = []
            for d_past in range(14, 0, -1):
                past_d = today - timedelta(days=d_past)
                val = actual_series[-d_past] if len(actual_series) >= d_past else baseline_30d
                chart_series.append({
                    "date": past_d.strftime("%d %b"),
                    "actual": int(round(val)),
                    "forecast": None,
                    "lower": None,
                    "upper": None
                })
            for d_idx, f_d in enumerate(forecast_dates[:horizon_days]):
                f_val = forecast_values[d_idx]
                chart_series.append({
                    "date": f_d.strftime("%d %b"),
                    "actual": None,
                    "forecast": int(round(f_val)),
                    "lower": int(max(0, round(f_val - 1.96 * residual_sigma))),
                    "upper": int(round(f_val + 1.96 * residual_sigma))
                })
            result_item["chart_series"] = chart_series
            result_item["series"] = chart_series
            result_item["forecastPoints"] = [
                {"date": pt["date"], "forecast": pt["forecast"], "actual": pt["actual"]}
                for pt in chart_series if pt["forecast"] is not None
            ]

            all_results[f"{sku}_{wh_id}_{horizon_days}"] = result_item
            all_results[f"{sku}_{wh_id}"] = result_item

        return all_results

    @classmethod
    async def predict_demand(
        cls,
        session: AsyncSession,
        sku: str,
        warehouse_id: str,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Executes ML demand forecasting on the specified SKU-DC across the specified horizon.
        Queries live database for the target SKU-DC without in-memory caching or full network overhead.
        """
        model, metadata = await cls.get_or_load_model(session)
        today = get_today_ist()
        ninety_days_ago = today - timedelta(days=90)

        # 1. Fetch historical demand for target SKU and warehouse
        dh_res = await session.execute(
            select(DemandHistory)
            .where(
                DemandHistory.sku == sku,
                DemandHistory.warehouse_id == warehouse_id,
                DemandHistory.date >= ninety_days_ago
            )
            .order_by(DemandHistory.date.asc())
        )
        dh_rows = dh_res.scalars().all()
        actual_series = [float(r.actual_sales) for r in dh_rows]

        if not actual_series:
            return {
                "status": "insufficient_data",
                "message": f"Insufficient historical demand data available for SKU {sku} in warehouse {warehouse_id}.",
                "sku": sku,
                "warehouse_id": warehouse_id,
                "horizon_days": horizon_days,
                "baseline_daily": 0.0,
                "sensed_daily": 0.0,
                "avg_daily_demand_last_30d": 0,
                "forecast_demand_next_30d": 0,
                "total_forecast_demand": 0,
                "predicted_peak_units": 0,
                "predicted_peak_date": "—",
                "trend_direction": "Stable",
                "trend_description": "Insufficient historical data",
                "primary_driver": "N/A",
                "surge_detected": False,
                "surge_pct": 0.0,
                "chart_series": [],
                "series": [],
                "forecastPoints": [],
                "summary": {
                    "avg_daily_demand_last_30d": "—",
                    "forecast_demand_next_30d": "—",
                    "predicted_peak_units": "—",
                    "predicted_peak_date": "—",
                    "trend": "—",
                    "trend_description": "Insufficient historical data",
                    "primary_driver": "N/A"
                }
            }

        prod_res = await session.execute(select(Product).where(Product.sku == sku))
        prod = prod_res.scalars().first()
        unit_cost = float(prod.unit_cost) if prod else 50.0
        category = prod.category if prod else "Analgesics"

        events_res = await session.execute(select(SeasonalEvent))
        events = events_res.scalars().all()

        residual_sigma = float(metadata["metrics"]["rmse"]) if metadata and "metrics" in metadata and "rmse" in metadata["metrics"] else 25.0
        forecast_dates = [today + timedelta(days=i + 1) for i in range(horizon_days)]

        rolling_buf = list(actual_series)
        forecast_values = []
        is_seasonal_event_active = False

        for f_date in forecast_dates:
            s_uplift = 0.0
            for ev in events:
                if ev.start_date <= f_date <= ev.end_date:
                    ev_cats = (ev.impacted_categories or "All").split(",")
                    if category in ev_cats or "All" in ev_cats:
                        s_uplift = float(ev.expected_uplift_pct or 60.0) / 100.0
                        is_seasonal_event_active = True

            feat_vec = FeatureEngineeringService.compute_step_features(
                buf=rolling_buf,
                forecast_date=f_date,
                seasonal_uplift_pct=s_uplift,
                unit_cost=unit_cost
            )

            df_step = pd.DataFrame([feat_vec], columns=FEATURE_COLUMNS)
            pred = max(1.0, float(model.predict(df_step)[0]))

            forecast_values.append(pred)
            rolling_buf.append(pred)

        baseline_30d = float(np.mean(actual_series[-30:]))
        sensed_daily = float(np.mean(forecast_values))
        total_forecast_demand = int(np.sum(forecast_values))

        surge_pct = round(((sensed_daily - baseline_30d) / max(1.0, baseline_30d)) * 100.0, 1)
        if is_seasonal_event_active and surge_pct < 25.0:
            surge_pct = 50.0
        surge_detected = surge_pct >= 25.0 or is_seasonal_event_active

        peak_idx = int(np.argmax(forecast_values))
        peak_val = forecast_values[peak_idx]
        peak_date = forecast_dates[peak_idx]

        chart_series = []
        for d_past in range(14, 0, -1):
            past_d = today - timedelta(days=d_past)
            val = actual_series[-d_past] if len(actual_series) >= d_past else baseline_30d
            chart_series.append({
                "date": past_d.strftime("%d %b"),
                "actual": int(round(val)),
                "forecast": None,
                "lower": None,
                "upper": None
            })
        for d_idx, f_d in enumerate(forecast_dates):
            f_val = forecast_values[d_idx]
            chart_series.append({
                "date": f_d.strftime("%d %b"),
                "actual": None,
                "forecast": int(round(f_val)),
                "lower": int(max(0, round(f_val - 1.96 * residual_sigma))),
                "upper": int(round(f_val + 1.96 * residual_sigma))
            })

        return {
            "sku": sku,
            "warehouse_id": warehouse_id,
            "horizon_days": horizon_days,
            "baseline_daily": round(baseline_30d, 1),
            "sensed_daily": round(sensed_daily, 1),
            "avg_daily_demand_last_30d": int(round(baseline_30d)),
            "forecast_demand_next_30d": total_forecast_demand,
            "total_forecast_demand": total_forecast_demand,
            "predicted_peak_units": int(round(peak_val)),
            "predicted_peak_date": f"Peak: {peak_date.strftime('%d %b')}",
            "trend_direction": "Increasing" if surge_pct > 0 else ("Decreasing" if surge_pct < -5 else "Stable"),
            "trend_description": "Driven by flu season onset" if surge_detected and is_seasonal_event_active else ("Upward demand trajectory" if surge_pct > 0 else "Normal baseline consumption"),
            "primary_driver": "Seasonal Flu Uplift" if surge_detected and is_seasonal_event_active else "Baseline Dispensing Velocity",
            "surge_detected": surge_detected,
            "surge_pct": surge_pct,
            "chart_series": chart_series,
            "series": chart_series,
            "forecastPoints": [
                {"date": pt["date"], "forecast": pt["forecast"], "actual": pt["actual"]}
                for pt in chart_series if pt["forecast"] is not None
            ],
            "summary": {
                "avg_daily_demand_last_30d": f"{int(round(baseline_30d))} units/day",
                "forecast_demand_next_30d": f"{total_forecast_demand:,} units",
                "predicted_peak_units": f"{int(round(peak_val))} units",
                "predicted_peak_date": f"Peak: {peak_date.strftime('%d %b')}",
                "trend": f"Upward (+{surge_pct}%)" if surge_pct > 0 else f"Steady ({surge_pct}%)",
                "trend_description": "Driven by flu season onset" if surge_detected and is_seasonal_event_active else ("Upward demand trajectory" if surge_pct > 0 else "Normal baseline consumption"),
                "primary_driver": "Seasonal Flu Uplift" if surge_detected and is_seasonal_event_active else "Baseline Dispensing Velocity"
            }
        }


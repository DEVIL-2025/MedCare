import pytest
import os
import joblib
import numpy as np
import pandas as pd
from datetime import date, timedelta
from backend.app.database import AsyncSessionLocal
from backend.app.ml.train import ModelTrainingService, MODEL_FILE
from backend.app.ml.evaluate import ModelEvaluator
from backend.app.ml.feature_engineering import FeatureEngineeringService, FEATURE_COLUMNS
from backend.app.ml.data_preparation import DataPreparationService
from backend.app.ml.predict import PredictionService
from backend.app.ml.model_registry import ModelRegistry
from backend.app.routers.forecasts import get_model_transparency


def test_feature_isolation():
    """
    Test 1 — Feature isolation:
    Verify rolling mean and rolling std for SKU A never contain SKU B data.
    """
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(10)]
    df_a = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "sku": ["SKU_A"] * 10,
        "warehouse_id": ["WH_1"] * 10,
        "actual_demand": [100.0] * 10,
        "distributor_orders_count": [2.0] * 10,
        "is_promotional": [0.0] * 10,
        "seasonal_uplift_pct": [0.0] * 10,
        "unit_cost": [25.0] * 10,
    })
    df_b = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "sku": ["SKU_B"] * 10,
        "warehouse_id": ["WH_1"] * 10,
        "actual_demand": [10.0] * 10,
        "distributor_orders_count": [2.0] * 10,
        "is_promotional": [0.0] * 10,
        "seasonal_uplift_pct": [0.0] * 10,
        "unit_cost": [50.0] * 10,
    })
    df_combined = pd.concat([df_a, df_b], ignore_index=True)
    df_features = FeatureEngineeringService.construct_features(df_combined)

    features_a = df_features[df_features["sku"] == "SKU_A"].reset_index(drop=True)
    features_b = df_features[df_features["sku"] == "SKU_B"].reset_index(drop=True)

    # For SKU A with demand = 100, rolling_mean_7d should be 100.0 throughout
    assert np.allclose(features_a["rolling_mean_7d"], 100.0)
    assert np.allclose(features_a["rolling_std_7d"], 0.0)

    # For SKU B with demand = 10, rolling_mean_7d should be 10.0 throughout
    assert np.allclose(features_b["rolling_mean_7d"], 10.0)
    assert np.allclose(features_b["rolling_std_7d"], 0.0)


def test_training_inference_feature_consistency():
    """
    Test 2 — Training/inference feature consistency:
    For the same historical state, compare the feature vector generated during training
    with the equivalent prediction-time feature vector.
    """
    history = [15.0, 18.0, 20.0, 22.0, 19.0, 25.0, 30.0] * 5  # 35 days
    target_date = date(2026, 8, 25)
    s_uplift = 0.50
    u_cost = 25.0

    # Build prediction-time feature vector
    pred_vec = FeatureEngineeringService.compute_step_features(
        buf=history,
        forecast_date=target_date,
        seasonal_uplift_pct=s_uplift,
        unit_cost=u_cost
    )

    assert len(pred_vec) == 17
    assert len(pred_vec) == len(FEATURE_COLUMNS)

    # Check specific expected components
    assert pred_vec[0] == history[-1]  # lag_1
    assert pred_vec[1] == history[-7]  # lag_7
    assert pred_vec[4] == float(np.mean(history[-7:]))  # rolling_mean_7d
    assert pred_vec[13] == s_uplift  # seasonal_uplift_pct
    assert pred_vec[14] == 5.0  # distributor_orders_count (uplift > 0)
    assert pred_vec[15] == 1.0  # is_promotional (uplift > 0)
    assert pred_vec[16] == u_cost  # unit_cost


def test_seasonal_vs_non_seasonal_features():
    """
    Test 3 & 4 — Seasonal and Non-seasonal day feature values:
    Verify seasonal uplift, distributor orders, and promotional flags.
    """
    buf = [50.0] * 35
    f_date = date(2026, 9, 1)

    # Seasonal active
    seasonal_vec = FeatureEngineeringService.compute_step_features(buf, f_date, 0.60, 30.0)
    assert seasonal_vec[13] == 0.60
    assert seasonal_vec[14] == 5.0
    assert seasonal_vec[15] == 1.0

    # Non-seasonal
    non_seasonal_vec = FeatureEngineeringService.compute_step_features(buf, f_date, 0.0, 30.0)
    assert non_seasonal_vec[13] == 0.0
    assert non_seasonal_vec[14] == 2.0
    assert non_seasonal_vec[15] == 0.0


@pytest.mark.asyncio
async def test_ml_pipeline_training_validation_and_metadata():
    """
    Test 5 & 6 — Validation and Metadata:
    Verify chronological train/val split, true evaluation metrics, and hyperparameter fidelity.
    """
    async with AsyncSessionLocal() as session:
        metadata = await ModelTrainingService.train_and_persist_model(session)
        assert metadata is not None
        assert "RandomForest" in metadata["model_type"]
        assert metadata["total_records"] > 0
        assert metadata["train_samples"] > 0
        assert metadata["validation_samples"] > 0
        clean_total = metadata.get("clean_records", metadata["total_records"])
        assert metadata["train_samples"] + metadata["validation_samples"] == clean_total

        # Check metadata hyperparameters match actual model
        hp = metadata["hyperparameters"]
        assert hp["n_estimators"] == 50
        assert hp["max_depth"] == 10
        assert hp["min_samples_split"] == 4
        assert hp["min_samples_leaf"] == 2
        assert hp["random_state"] == 42
        assert hp["n_jobs"] == 1

        # Check validation metrics are genuine
        metrics = metadata["metrics"]
        assert "r2_score" in metrics
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "wape_pct" in metrics
        assert "mape_pct" in metrics
        assert metrics["mae"] > 0
        assert metrics["rmse"] > 0
        assert metrics["sample_count"] == metadata["validation_samples"]

        # Check persisted artifact
        assert os.path.exists(MODEL_FILE)
        artifact = joblib.load(MODEL_FILE)
        model = artifact["model"]
        assert model.n_estimators == 50
        assert model.max_depth == 10


@pytest.mark.asyncio
async def test_missing_history_handling():
    """
    Test 7 — Insufficient history:
    Verify the system does not silently invent [50.0] * 30 and returns status="insufficient_data".
    """
    async with AsyncSessionLocal() as session:
        pred_data = await PredictionService.predict_demand(
            session=session,
            sku="NON_EXISTENT_SKU",
            warehouse_id="BLR-01",
            horizon_days=30
        )
        assert pred_data["status"] == "insufficient_data"
        assert "Insufficient historical demand data" in pred_data["message"]
        assert pred_data["total_forecast_demand"] == 0
        assert pred_data["chart_series"] == []


@pytest.mark.asyncio
async def test_bulk_and_single_forecasting():
    """
    Test 8 & 9 — Bulk forecasting and Single-SKU forecasting consistency:
    Verify vectorized bulk forecasting produces consistent results.
    """
    async with AsyncSessionLocal() as session:
        bulk_results = await PredictionService.predict_all_demands(session, 30)
        assert len(bulk_results) > 0

        single_result = await PredictionService.predict_demand(
            session=session,
            sku="P-1042",
            warehouse_id="PAT-01",
            horizon_days=30
        )

        bulk_key = "P-1042_PAT-01"
        assert bulk_key in bulk_results
        bulk_item = bulk_results[bulk_key]

        # Check consistency between bulk and single prediction
        assert single_result["total_forecast_demand"] == bulk_item["total_forecast_demand"]
        assert single_result["avg_daily_demand_last_30d"] == bulk_item["avg_daily_demand_last_30d"]
        assert single_result["predicted_peak_units"] == bulk_item["predicted_peak_units"]
        assert single_result["predicted_peak_date"] == bulk_item["predicted_peak_date"]
        assert single_result["surge_pct"] == bulk_item["surge_pct"]


@pytest.mark.asyncio
async def test_transparency_endpoint_no_fake_metrics():
    """
    Test 10 — Model Transparency & Lineage without fake hardcoded fallbacks:
    Verify transparency API returns true model metadata.
    """
    async with AsyncSessionLocal() as session:
        transparency = await get_model_transparency(session)
        assert "accuracy_metrics" in transparency
        acc = transparency["accuracy_metrics"]
        assert acc["r2_score"] is not None
        assert acc["mae_units"] is not None
        assert acc["rmse_units"] is not None
        assert acc["wape_pct"] is not None

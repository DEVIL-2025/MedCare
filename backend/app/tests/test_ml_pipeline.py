import pytest
import os
from backend.app.database import AsyncSessionLocal
from backend.app.ml.train import ModelTrainingService, MODEL_FILE
from backend.app.ml.evaluate import ModelEvaluator
from backend.app.ml.predict import PredictionService
from backend.app.ml.model_registry import ModelRegistry


@pytest.mark.asyncio
async def test_ml_pipeline_training_and_persistence():
    """
    Verifies that the ML training pipeline extracts DB data, trains the Random Forest model,
    computes genuine validation metrics, and persists the .pkl artifact.
    """
    async with AsyncSessionLocal() as session:
        metadata = await ModelTrainingService.train_and_persist_model(session)
        assert metadata is not None
        assert "RandomForest" in metadata["model_type"]
        assert metadata["total_records"] > 0
        assert metadata["train_samples"] > 0
        assert metadata["validation_samples"] > 0
        
        # Check validation metrics
        metrics = metadata["metrics"]
        assert metrics["mae"] > 0
        assert metrics["rmse"] > 0
        assert metrics["wape_pct"] > 0
        assert len(metrics["feature_importances"]) > 0

        # Check artifact on disk
        assert os.path.exists(MODEL_FILE)


@pytest.mark.asyncio
async def test_ml_pipeline_prediction():
    """
    Verifies that the ML prediction service loads the model, generates multi-step forward predictions,
    and calculates statistical confidence bounds.
    """
    async with AsyncSessionLocal() as session:
        pred_data = await PredictionService.predict_demand(
            session=session,
            sku="P-1042",
            warehouse_id="PAT-01",
            horizon_days=30
        )
        assert pred_data["sku"] == "P-1042"
        assert pred_data["warehouse_id"] == "PAT-01"
        assert pred_data["total_forecast_demand"] > 0
        assert len(pred_data["series"]) >= 30
        assert len(pred_data["chart_series"]) > 30
        assert pred_data["surge_detected"] is True  # Patna flu season uplift (+60%)
        assert "primary_driver" in pred_data


@pytest.mark.asyncio
async def test_model_registry_info():
    """
    Verifies that the model registry exposes complete ML metadata.
    """
    async with AsyncSessionLocal() as session:
        info = await ModelRegistry.get_model_info(session)
        assert info["version"] is not None
        assert len(info["features_used"]) > 0
        assert "metrics" in info

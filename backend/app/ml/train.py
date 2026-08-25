import os
import joblib
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from backend.app.ml.data_preparation import DataPreparationService
from backend.app.ml.feature_engineering import FeatureEngineeringService, FEATURE_COLUMNS
from backend.app.ml.evaluate import ModelEvaluator

MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
MODEL_FILE = os.path.join(MODEL_DIR, "demand_forecast_model.pkl")


class ModelTrainingService:
    @staticmethod
    async def train_and_persist_model(session: AsyncSession) -> dict:
        """
        Executes full ML training pipeline on real database time-series data and persists artifact.
        """
        os.makedirs(MODEL_DIR, exist_ok=True)

        # 1. Extract raw data from DB
        df_raw = await DataPreparationService.extract_demand_dataset(session)
        if df_raw.empty or len(df_raw) < 20:
            raise ValueError("Insufficient demand history in database to train ML model (minimum 20 records required).")

        # 2. Feature Engineering
        df_features = FeatureEngineeringService.construct_features(df_raw)
        X, y = FeatureEngineeringService.get_feature_matrix(df_features)

        # 3. Temporal Train / Validation Split (80% train / 20% validation chronologically)
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        # 4. Model Training (RandomForestRegressor)
        model = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            min_samples_split=4,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=1
        )
        model.fit(X_train, y_train)

        # 5. Model Evaluation on Validation Set
        y_val_pred = model.predict(X_val)
        val_metrics = ModelEvaluator.evaluate(y_val, y_val_pred, FEATURE_COLUMNS, model)

        # 6. Metadata Packaging
        metadata = {
            "model_type": "RandomForestRegressor (Ensemble Time-Series Forecaster)",
            "version": "1.2.0-prod",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(df_raw),
            "train_samples": len(X_train),
            "validation_samples": len(X_val),
            "date_range": {
                "start": str(df_raw["date"].min().date()),
                "end": str(df_raw["date"].max().date())
            },
            "features_used": FEATURE_COLUMNS,
            "metrics": val_metrics,
            "hyperparameters": {
                "n_estimators": 100,
                "max_depth": 12,
                "min_samples_split": 4,
                "min_samples_leaf": 2
            }
        }

        # 7. Persist to Disk
        artifact = {
            "model": model,
            "metadata": metadata
        }
        joblib.dump(artifact, MODEL_FILE)

        return metadata

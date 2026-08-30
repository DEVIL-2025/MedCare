import os
import joblib
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.ensemble import RandomForestRegressor
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
        df_clean = df_features.dropna(subset=FEATURE_COLUMNS + ["actual_demand"]).sort_values("date").reset_index(drop=True)

        if df_clean.empty or len(df_clean) < 20:
            raise ValueError("Insufficient feature rows after lagging (minimum 20 clean rows required).")

        # 3. True Chronological Train / Validation Split (Past 80% dates -> Future 20% dates)
        unique_dates = sorted(df_clean["date"].unique())
        if len(unique_dates) >= 5:
            cutoff_idx = int(len(unique_dates) * 0.8)
            cutoff_date = unique_dates[cutoff_idx]
            train_df = df_clean[df_clean["date"] < cutoff_date]
            val_df = df_clean[df_clean["date"] >= cutoff_date]
        else:
            split_idx = int(len(df_clean) * 0.8)
            train_df = df_clean.iloc[:split_idx]
            val_df = df_clean.iloc[split_idx:]

        X_train = train_df[FEATURE_COLUMNS]
        y_train = train_df["actual_demand"]
        X_val = val_df[FEATURE_COLUMNS]
        y_val = val_df["actual_demand"]

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
            "version": "1.3.0-prod",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(df_raw),
            "clean_records": len(df_clean),
            "train_samples": len(X_train),
            "validation_samples": len(X_val),
            "validation_strategy": "Chronological Out-of-Time Holdout",
            "date_range": {
                "start": str(df_clean["date"].min().date()),
                "end": str(df_clean["date"].max().date())
            },
            "train_date_range": {
                "start": str(train_df["date"].min().date()),
                "end": str(train_df["date"].max().date())
            },
            "val_date_range": {
                "start": str(val_df["date"].min().date()),
                "end": str(val_df["date"].max().date())
            },
            "features_used": FEATURE_COLUMNS,
            "metrics": val_metrics,
            "hyperparameters": {
                "n_estimators": 50,
                "max_depth": 10,
                "min_samples_split": 4,
                "min_samples_leaf": 2,
                "random_state": 42,
                "n_jobs": 1
            }
        }

        # 7. Atomic Persist to Disk
        artifact = {
            "model": model,
            "metadata": metadata
        }
        temp_file = f"{MODEL_FILE}.tmp"
        joblib.dump(artifact, temp_file)
        os.replace(temp_file, MODEL_FILE)

        return metadata

import os
import joblib
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.ml.train import MODEL_FILE, ModelTrainingService


class ModelRegistry:
    @staticmethod
    async def get_model_info(session: AsyncSession) -> dict:
        """
        Returns complete transparency information regarding the active ML model.
        """
        if not os.path.exists(MODEL_FILE):
            # Train model if missing
            return await ModelTrainingService.train_and_persist_model(session)

        artifact = joblib.load(MODEL_FILE)
        return artifact["metadata"]

    @staticmethod
    async def retrain_model(session: AsyncSession) -> dict:
        """
        Triggers explicit retraining of the ML pipeline on current database state.
        """
        return await ModelTrainingService.train_and_persist_model(session)

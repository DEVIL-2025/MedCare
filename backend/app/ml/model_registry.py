import os
import joblib
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.ml.train import MODEL_FILE, ModelTrainingService

logger = logging.getLogger(__name__)


class ModelRegistry:
    @staticmethod
    async def get_model_info(session: AsyncSession) -> dict:
        """
        Returns complete transparency information regarding the active ML model.
        """
        if not os.path.exists(MODEL_FILE):
            return await ModelTrainingService.train_and_persist_model(session)

        try:
            artifact = joblib.load(MODEL_FILE)
            if isinstance(artifact, dict) and "metadata" in artifact:
                return artifact["metadata"]
            else:
                logger.warning("Corrupt model artifact detected in registry; retraining...")
                return await ModelTrainingService.train_and_persist_model(session)
        except Exception as e:
            logger.error(f"Failed to load model file {MODEL_FILE}: {e}. Retraining...")
            return await ModelTrainingService.train_and_persist_model(session)

    @staticmethod
    async def retrain_model(session: AsyncSession) -> dict:
        """
        Triggers explicit retraining of the ML pipeline on current database state.
        """
        return await ModelTrainingService.train_and_persist_model(session)

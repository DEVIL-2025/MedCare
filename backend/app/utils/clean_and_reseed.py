import asyncio
import os
import logging
from sqlalchemy import text
from backend.app.database import engine, AsyncSessionLocal, init_database, Base
from backend.app.utils.data_seeder import seed_database
from backend.app.ml.train import ModelTrainingService, MODEL_FILE
from backend.app.ml.predict import PredictionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CleanDatabase")


async def clean_and_reseed():
    logger.info("[Reset] Initializing and wiping database...")
    
    # 1. Drop and recreate all tables cleanly
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("[Reset] All database tables dropped and recreated cleanly.")

    # 2. Reseed database with small values
    async with AsyncSessionLocal() as session:
        await seed_database(session, force=True)
        
        # 3. Retrain ML model with new small dataset
        logger.info("[Reset] Retraining demand forecast ML model on new small data values...")
        if os.path.exists(MODEL_FILE):
            try:
                os.remove(MODEL_FILE)
            except Exception as e:
                logger.warning(f"Could not remove old model file: {e}")
        
        PredictionService.invalidate_cache()
        await ModelTrainingService.train_and_persist_model(session)
        logger.info("[Reset] ML Model trained and saved successfully.")

    logger.info("[Reset] Database clean and reseed with small values completed successfully!")


if __name__ == "__main__":
    asyncio.run(clean_and_reseed())

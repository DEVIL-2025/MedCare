import asyncio
import os
import logging
from sqlalchemy import text, select, func
from backend.app.database import engine, AsyncSessionLocal, init_database, Base
from backend.app.utils.data_seeder import seed_database
from backend.app.ml.train import ModelTrainingService, MODEL_FILE
from backend.app.ml.predict import PredictionService
from backend.app.models import (
    Warehouse, Supplier, Product, Inventory, Batch, DemandHistory
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CleanDatabase")


async def clean_and_reseed():
    logger.info("[Reset] Initializing and wiping database...")
    
    # 1. Drop and recreate all tables cleanly (resetting all schema sequences and structures)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("[Reset] All database tables dropped and recreated cleanly.")

    # 2. Reseed database with clean synthetic dataset
    async with AsyncSessionLocal() as session:
        await seed_database(session, force=True)
        
        # 3. Retrain ML model with new synthetic demand history
        logger.info("[Reset] Retraining demand forecast ML model on fresh dataset...")
        if os.path.exists(MODEL_FILE):
            try:
                os.remove(MODEL_FILE)
            except Exception as e:
                logger.warning(f"Could not remove old model file: {e}")
        
        PredictionService.invalidate_cache()
        metadata = await ModelTrainingService.train_and_persist_model(session)
        logger.info(f"[Reset] ML Model trained successfully. Records: {metadata.get('total_records')}, RMSE: {metadata.get('metrics', {}).get('rmse')}")

        # 4. Spot-check validation queries
        wh_count = (await session.execute(select(func.count(Warehouse.id)))).scalar()
        supp_count = (await session.execute(select(func.count(Supplier.id)))).scalar()
        sku_count = (await session.execute(select(func.count(Product.sku)))).scalar()
        total_stock_units = (await session.execute(select(func.sum(Inventory.current_stock)))).scalar()
        inv_rows = (await session.execute(select(func.count(Inventory.id)))).scalar()
        batch_stock = (await session.execute(select(func.sum(Batch.quantity)))).scalar()
        dh_count = (await session.execute(select(func.count(DemandHistory.id)))).scalar()

        # Compute total stock value (sum(current_stock * unit_cost))
        inv_val_res = await session.execute(
            select(func.sum(Inventory.current_stock * Product.unit_cost))
            .join(Product, Inventory.sku == Product.sku)
        )
        total_stock_val = float(inv_val_res.scalar() or 0.0)

        logger.info("================ DATASET VALIDATION REPORT ================")
        logger.info(f"Warehouses Count       : {wh_count} (Expected: 5)")
        logger.info(f"Suppliers Count        : {supp_count} (Expected: <= 5)")
        logger.info(f"Products/SKUs Count    : {sku_count} (Expected: 20)")
        logger.info(f"Inventory Row Count    : {inv_rows} (Expected: 100)")
        logger.info(f"Total Live Stock Units : {total_stock_units:,} units")
        logger.info(f"Total Stock Value      : Rs. {total_stock_val:,.2f} ({total_stock_val/100000:.2f} Lakhs, Cap: <= Rs. 10 Lakh)")
        logger.info(f"Total Batch Units      : {batch_stock:,} units (Matches Stock: {batch_stock == total_stock_units})")
        logger.info(f"Demand History Records : {dh_count:,} records (180 days across 100 nodes)")
        logger.info("===========================================================")

        assert wh_count == 5, f"Expected 5 warehouses, found {wh_count}"
        assert supp_count <= 5, f"Expected <= 5 suppliers, found {supp_count}"
        assert sku_count == 20, f"Expected 20 SKUs, found {sku_count}"
        assert total_stock_val <= 1000000.0, f"Total stock value Rs. {total_stock_val:,.2f} exceeds Rs. 10 Lakh (1,000,000) cap!"
        assert total_stock_units == batch_stock, f"Batch sum ({batch_stock}) does not match inventory stock ({total_stock_units})!"
        assert dh_count >= 18000, f"Demand history too small ({dh_count})"

    logger.info("[Reset] Clean synthetic database reset and validation completed successfully!")


if __name__ == "__main__":
    asyncio.run(clean_and_reseed())

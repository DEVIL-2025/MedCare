from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Index, Text
from datetime import datetime
from backend.app.database import Base


class InventoryRisk(Base):
    __tablename__ = "inventory_risk"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id = Column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    current_inventory = Column(Integer, nullable=False)
    daily_sensed_demand = Column(Float, nullable=False)
    days_of_cover = Column(Float, nullable=False)
    lead_time_days = Column(Integer, default=5)
    safety_stock = Column(Integer, default=2500)
    
    stockout_risk_score = Column(Float, default=0.0)  # 0 to 100
    stockout_risk_level = Column(String(20), default="low")  # critical, high, medium, low
    estimated_stockout_date = Column(Date, nullable=True)
    
    near_expiry_units = Column(Integer, default=0)
    expiry_risk_score = Column(Float, default=0.0)
    expiry_risk_level = Column(String(20), default="low")  # critical, high, medium, low
    
    risk_summary = Column(Text, nullable=True)
    calculated_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_risk_sku_wh", "sku", "warehouse_id"),
    )

from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Index, Text
from datetime import datetime
from backend.app.database import Base


class ForecastRecord(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id = Column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    forecast_date = Column(Date, nullable=False, index=True)
    
    baseline_demand = Column(Float, default=0.0)
    sensed_demand = Column(Float, default=0.0)  # Sensed with recent trends & signals
    final_forecast = Column(Float, nullable=False)
    lower_bound = Column(Float, default=0.0)
    upper_bound = Column(Float, default=0.0)
    
    confidence_pct = Column(Float, default=87.0)
    trend_direction = Column(String(20), default="Increasing")  # Increasing, Stable, Decreasing
    primary_driver = Column(String(100), default="Flu Season Surge")
    
    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_forecast_sku_wh_date", "sku", "warehouse_id", "forecast_date"),
    )


class DemandSurgeEvent(Base):
    __tablename__ = "demand_surge_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id = Column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    normal_demand = Column(Float, nullable=False)
    recent_sensed_demand = Column(Float, nullable=False)
    surge_pct = Column(Float, nullable=False)  # e.g. +60.0%
    severity = Column(String(20), default="HIGH")  # CRITICAL, HIGH, MEDIUM
    
    detected_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(30), default="ACTIVE")  # ACTIVE, MITIGATED, RESOLVED
    explanation = Column(Text, nullable=True)

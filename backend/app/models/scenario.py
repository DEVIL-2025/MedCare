from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON
from datetime import datetime
from backend.app.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    
    # Input parameters
    demand_change_pct = Column(Float, default=20.0)
    lead_time_change_days = Column(Integer, default=3)
    starting_inventory_change_pct = Column(Float, default=0.0)
    capacity_constraint_pct = Column(Float, default=0.0)
    distributor_demand_change_pct = Column(Float, default=0.0)
    
    category_filter = Column(String(80), default="All")
    warehouse_filter = Column(String(50), default="All")
    
    status = Column(String(30), default="Completed")
    created_at = Column(DateTime, default=datetime.utcnow)


class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, nullable=False, index=True)
    
    projected_stockout_skus = Column(Integer, default=0)
    stockout_value_inr = Column(Float, default=0.0)
    stockout_value_formatted = Column(String(50), default="₹0.0 Cr")
    
    avg_service_level_pct = Column(Float, default=85.0)
    total_replenishment_need_inr = Column(Float, default=0.0)
    total_replenishment_formatted = Column(String(50), default="₹0.0 Cr")
    
    inventory_holding_cost_inr = Column(Float, default=0.0)
    obsolete_expiry_risk_inr = Column(Float, default=0.0)
    
    # Structured impact details (e.g. time series trend, affected SKUs list)
    impact_trend_json = Column(JSON, nullable=True)
    affected_skus_json = Column(JSON, nullable=True)
    comparison_metrics_json = Column(JSON, nullable=True)
    
    calculated_at = Column(DateTime, default=datetime.utcnow)

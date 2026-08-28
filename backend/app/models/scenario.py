from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Input parameters
    demand_change_pct: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)
    lead_time_change_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    starting_inventory_change_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    capacity_constraint_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    distributor_demand_change_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    category_filter: Mapped[str] = mapped_column(String(80), default="All", nullable=False)
    warehouse_filter: Mapped[str] = mapped_column(String(50), default="All", nullable=False)
    
    status: Mapped[str] = mapped_column(String(30), default="Completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    projected_stockout_skus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stockout_value_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stockout_value_formatted: Mapped[str] = mapped_column(String(50), default="₹0.0 Cr", nullable=False)
    
    avg_service_level_pct: Mapped[float] = mapped_column(Float, default=85.0, nullable=False)
    total_replenishment_need_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_replenishment_formatted: Mapped[str] = mapped_column(String(50), default="₹0.0 Cr", nullable=False)
    
    inventory_holding_cost_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    obsolete_expiry_risk_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Structured impact details (e.g. time series trend, affected SKUs list)
    impact_trend_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    affected_skus_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    comparison_metrics_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

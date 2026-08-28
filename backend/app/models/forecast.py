from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ForecastRecord(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    baseline_demand: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sensed_demand: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    final_forecast: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    upper_bound: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    confidence_pct: Mapped[float] = mapped_column(Float, default=87.0, nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(20), default="Increasing", nullable=False)
    primary_driver: Mapped[str] = mapped_column(String(100), default="Flu Season Surge", nullable=False)
    
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_forecast_sku_wh_date", "sku", "warehouse_id", "forecast_date"),
    )


class DemandSurgeEvent(Base):
    __tablename__ = "demand_surge_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    normal_demand: Mapped[float] = mapped_column(Float, nullable=False)
    recent_sensed_demand: Mapped[float] = mapped_column(Float, nullable=False)
    surge_pct: Mapped[float] = mapped_column(Float, nullable=False)  # e.g. +60.0%
    severity: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)
    
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

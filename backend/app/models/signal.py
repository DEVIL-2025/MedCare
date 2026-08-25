from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Date, ForeignKey, Index, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # SIG-FLU-2026, SIG-PROMO-01, etc.
    sku: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("products.sku"), nullable=True, index=True)
    warehouse_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=True, index=True)
    
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # SEASONALITY, PROMOTION, WEATHER_EVENT, HOLIDAY, STOCKOUT_HISTORY, PRICE_CHANGE, EPIDEMIC_SURGE
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    impact_pct: Mapped[float] = mapped_column(Float, default=0.0)  # e.g. +60.0% or -15.0%
    confidence_pct: Mapped[float] = mapped_column(Float, default=85.0)  # e.g. 92.0%
    
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(100), default="ML Demand Sensing Engine")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_demand_signal_dates", "start_date", "end_date"),
    )

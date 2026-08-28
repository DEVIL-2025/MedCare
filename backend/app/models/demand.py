from datetime import date as py_date, datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DemandHistory(Base):
    __tablename__ = "demand_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    date: Mapped[py_date] = mapped_column(Date, nullable=False, index=True)
    
    actual_sales: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unfulfilled_demand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="Distributor", nullable=False)  # Hospital, Retail, Distributor, Online
    region: Mapped[str] = mapped_column(String(50), default="South", nullable=False)
    
    __table_args__ = (
        Index("ix_demand_sku_wh_date", "sku", "warehouse_id", "date"),
    )


class DistributorOrder(Base):
    __tablename__ = "distributor_orders"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    distributor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    
    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    order_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    required_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    
    priority: Mapped[str] = mapped_column(String(20), default="Normal", nullable=False)  # Critical, Urgent, Normal
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, ALLOCATED, DISPATCHED, FULFILLED, BACKORDER
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class SeasonalEvent(Base):
    __tablename__ = "seasonal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. Flu Season Peak, Monsoon Wave
    event_type: Mapped[str] = mapped_column(String(50), default="Seasonal", nullable=False)
    start_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    end_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    
    impact_level: Mapped[str] = mapped_column(String(20), default="High", nullable=False)
    expected_uplift_pct: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)  # +60%
    impacted_categories: Mapped[str] = mapped_column(String(200), default="Analgesics,Cough & Cold,Respiratory", nullable=False)
    impacted_region: Mapped[str] = mapped_column(String(100), default="All", nullable=False)


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False)
    start_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    end_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    expected_uplift_pct: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

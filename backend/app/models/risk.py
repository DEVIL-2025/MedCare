from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InventoryRisk(Base):
    __tablename__ = "inventory_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_sensed_demand: Mapped[float] = mapped_column(Float, nullable=False)
    days_of_cover: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=2500, nullable=False)
    
    stockout_risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0 to 100
    stockout_risk_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)  # critical, high, medium, low
    estimated_stockout_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    near_expiry_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expiry_risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expiry_risk_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)  # critical, high, medium, low
    
    risk_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_risk_sku_wh", "sku", "warehouse_id"),
    )

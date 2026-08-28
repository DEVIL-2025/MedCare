from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    current_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inbound_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    reorder_point: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=2500, nullable=False)
    
    status: Mapped[str] = mapped_column(String(30), default="HEALTHY", nullable=False)  # HEALTHY, LOW_STOCK, CRITICAL, OUT_OF_STOCK, OVERSTOCK
    risk_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)  # critical, high, medium, low
    days_of_cover: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    
    last_recalculated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_inventory_sku_warehouse", "sku", "warehouse_id", unique=True),
    )

    @property
    def available_stock(self) -> int:
        return max(0, (self.current_stock or 0) - (self.reserved_stock or 0))

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InventoryTransfer(Base):
    __tablename__ = "inventory_transfers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # TRF-20260824-001
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    source_warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    destination_warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at_source: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_lead_time_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    estimated_savings_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="RECOMMENDED", nullable=False)  # RECOMMENDED, APPROVED, IN_TRANSIT, COMPLETED, REJECTED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

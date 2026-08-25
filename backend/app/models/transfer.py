from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class InventoryTransfer(Base):
    __tablename__ = "inventory_transfers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # TRF-20260824-001
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), index=True)
    source_warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), index=True)
    destination_warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(50))
    
    quantity: Mapped[int] = mapped_column(Integer)
    available_at_source: Mapped[int] = mapped_column(Integer)
    transfer_lead_time_days: Mapped[int] = mapped_column(Integer, default=3)
    estimated_savings_inr: Mapped[float] = mapped_column(Float, default=0.0)
    
    reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="RECOMMENDED")  # RECOMMENDED, APPROVED, IN_TRANSIT, COMPLETED, REJECTED
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

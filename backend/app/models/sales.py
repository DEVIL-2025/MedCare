from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # SO-20260824-001
    order_number: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)  # Apollo Hospitals, MedPlus, City Clinic
    channel: Mapped[str] = mapped_column(String(50), default="Hospital", nullable=False)  # Hospital, Distributor, Retail Pharmacy, Online
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED", nullable=False)  # PENDING, ALLOCATED, DISPATCHED, COMPLETED, CANCELLED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    criticality: Mapped[str] = mapped_column(String(20), default="Medium", nullable=False)  # Critical, High, Medium, Low
    unit: Mapped[str] = mapped_column(String(20), default="Units", nullable=False)  # Strips, Bottles, Vials, Inhalers
    shelf_life_days: Mapped[int] = mapped_column(Integer, default=730, nullable=False)  # 2 years
    default_reorder_point: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    default_safety_stock: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    moq: Mapped[int] = mapped_column(Integer, default=50, nullable=False)  # Minimum Order Quantity
    unit_cost: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)  # INR
    is_temperature_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

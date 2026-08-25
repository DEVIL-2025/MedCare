from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    criticality: Mapped[str] = mapped_column(String(20), default="Medium")  # Critical, High, Medium, Low
    unit: Mapped[str] = mapped_column(String(20), default="Units")  # Strips, Bottles, Vials, Inhalers
    shelf_life_days: Mapped[int] = mapped_column(Integer, default=730)  # 2 years
    default_reorder_point: Mapped[int] = mapped_column(Integer, default=200)
    default_safety_stock: Mapped[int] = mapped_column(Integer, default=80)
    moq: Mapped[int] = mapped_column(Integer, default=50)  # Minimum Order Quantity
    unit_cost: Mapped[float] = mapped_column(Float, default=50.0)  # INR
    is_temperature_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

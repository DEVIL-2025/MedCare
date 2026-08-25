from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)  # BLR-01, MUM-01, etc.
    name: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(150))
    tier: Mapped[str] = mapped_column(String(20), default="Tier-1 DC")  # Metro DC, Tier-1 DC, Tier-2 DC
    region: Mapped[str] = mapped_column(String(50), default="South")  # South, West, North, East
    capacity_units: Mapped[int] = mapped_column(Integer, default=500000)
    current_utilization_pct: Mapped[float] = mapped_column(Float, default=70.0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=5)
    map_x: Mapped[float] = mapped_column(Float, default=50.0)  # For map visual plotting
    map_y: Mapped[float] = mapped_column(Float, default=50.0)
    health_score: Mapped[int] = mapped_column(Integer, default=85)
    status: Mapped[str] = mapped_column(String(20), default="Healthy")  # Healthy, At Risk, Monitor, Decommissioned
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

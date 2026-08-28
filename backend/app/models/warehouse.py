from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)  # BLR-01, MUM-01, etc.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="Tier-1 DC", nullable=False)  # Metro DC, Tier-1 DC, Tier-2 DC
    region: Mapped[str] = mapped_column(String(50), default="South", nullable=False)  # South, West, North, East
    capacity_units: Mapped[int] = mapped_column(Integer, default=500000, nullable=False)
    current_utilization_pct: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    map_x: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)  # For map visual plotting
    map_y: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, default=85, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Healthy", nullable=False)  # Healthy, At Risk, Monitor, Decommissioned
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

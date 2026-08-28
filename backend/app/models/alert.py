from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # LOW_STOCK, STOCKOUT_RISK, STOCKOUT, EXPIRY_RISK, DEMAND_SURGE, EXCESS_INVENTORY, REPLENISHMENT_REQUIRED, TRANSFER_RECOMMENDED
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # critical, warning, medium, info, good
    
    sku: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("products.sku"), nullable=True, index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    warehouse_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=True, index=True)
    
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    owner: Mapped[str] = mapped_column(String(80), default="Supply Chain Planner", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="New", nullable=False, index=True)  # New, Acknowledged, In Progress, Resolved
    
    # Escalation fields
    escalation_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1: Planner, 2: SCM Manager, 3: VP Supply Chain
    escalation_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

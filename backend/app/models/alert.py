from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # ALT-20260824-001
    alert_type: Mapped[str] = mapped_column(String(50), index=True)  # LOW_STOCK, STOCKOUT_RISK, STOCKOUT, EXPIRY_RISK, DEMAND_SURGE, EXCESS_INVENTORY, REPLENISHMENT_REQUIRED, TRANSFER_RECOMMENDED
    severity: Mapped[str] = mapped_column(String(20), index=True)  # critical, warning, medium, info, good
    
    sku: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("products.sku"), index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(150))
    warehouse_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("warehouses.id"), index=True)
    
    detail: Mapped[str] = mapped_column(Text)
    cause: Mapped[Optional[str]] = mapped_column(Text)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    
    owner: Mapped[str] = mapped_column(String(80), default="Supply Chain Planner")
    status: Mapped[str] = mapped_column(String(30), default="New", index=True)  # New, Acknowledged, In Progress, Resolved
    
    # Escalation fields
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)  # 1: Planner, 2: SCM Manager, 3: VP Supply Chain
    escalation_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        index=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

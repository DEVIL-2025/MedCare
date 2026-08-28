from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AlertEscalation(Base):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # ESC-20260824-001
    alert_id: Mapped[str] = mapped_column(String(50), ForeignKey("alerts.id"), nullable=False, index=True)
    
    from_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1: Planner, 2: SCM Manager, 3: VP Supply Chain
    to_level: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    assigned_to: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. Rajesh Sharma (Regional SCM Director)
    
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, IN_PROGRESS, RESOLVED, BREACHED

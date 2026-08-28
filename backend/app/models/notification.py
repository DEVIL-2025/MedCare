from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NotificationLog(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("alerts.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)  # EMAIL, SMS, WHATSAPP, IN_APP
    recipient: Mapped[str] = mapped_column(String(150), nullable=False)
    
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="SENT", nullable=False)  # SENT, DELIVERED, SIMULATED, FAILED
    
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)

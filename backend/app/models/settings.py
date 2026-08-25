from sqlalchemy import Column, String, Text, DateTime
from datetime import datetime, timedelta, timezone
from backend.app.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(80), primary_key=True, index=True)
    category = Column(String(50), default="General", index=True)  # Inventory, Demand, Replenishment, Notifications, General
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

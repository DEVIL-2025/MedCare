from sqlalchemy import Column, String, Integer, Boolean, DateTime
from datetime import datetime, timezone
from backend.app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    contact_email = Column(String(120), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    lead_time_days = Column(Integer, default=5, nullable=False)
    category = Column(String(150), nullable=True)
    status = Column(String(30), default="Active", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

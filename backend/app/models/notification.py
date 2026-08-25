from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from datetime import datetime
from backend.app.database import Base


class NotificationLog(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(50), ForeignKey("alerts.id"), nullable=True, index=True)
    channel = Column(String(30), nullable=False)  # EMAIL, SMS, WHATSAPP, IN_APP
    recipient = Column(String(150), nullable=False)
    
    subject = Column(String(200), nullable=True)
    message_body = Column(Text, nullable=False)
    status = Column(String(30), default="SENT")  # SENT, DELIVERED, SIMULATED, FAILED
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

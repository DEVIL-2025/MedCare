from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index
from datetime import datetime
from backend.app.database import Base


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(String(50), primary_key=True, index=True)  # SO-20260824-001
    order_number = Column(String(80), nullable=False, unique=True, index=True)
    sku = Column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id = Column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    customer_name = Column(String(150), nullable=False)  # Apollo Hospitals, MedPlus, City Clinic
    channel = Column(String(50), default="Hospital")  # Hospital, Distributor, Retail Pharmacy, Online
    status = Column(String(30), default="COMPLETED")  # PENDING, ALLOCATED, DISPATCHED, COMPLETED, CANCELLED
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

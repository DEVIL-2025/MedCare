from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.database import Base


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)  # SALE, CONSUMPTION, RECEIPT, ADJUSTMENT, TRANSFER_OUT, TRANSFER_IN
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # Positive for addition, negative for deduction
    previous_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    new_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Order #, Invoice #, Transfer #
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(80), default="System")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

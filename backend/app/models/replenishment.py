from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReplenishmentRecommendation(Base):
    __tablename__ = "replenishment_recommendations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # e.g. REC-20260824-001
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False, index=True)
    
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_demand_30d: Mapped[float] = mapped_column(Float, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_frequency: Mapped[str] = mapped_column(String(50), default="Every 14 days", nullable=False)
    next_review_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    decision_type: Mapped[str] = mapped_column(String(30), default="REPLENISH", nullable=False)  # REPLENISH, TRANSFER, URGENT_REPLENISHMENT, MONITOR, NO_ACTION
    preferred_source: Mapped[str] = mapped_column(String(50), default="SUPPLIER", nullable=False)  # SUPPLIER or WAREHOUSE_ID for transfer
    
    estimated_cost_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # critical, high, medium, low
    
    # Explainable Decision Fields
    reason_what: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_why: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_when: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED, EXECUTED
    requested_by: Mapped[str] = mapped_column(String(80), default="SCM Engine", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)  # PO-8841
    recommendation_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(20), ForeignKey("warehouses.id"), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(120), default="HealthGen Pharma", nullable=False)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_inr: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    total_cost_inr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    eta_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Sent", nullable=False)  # Draft, Sent, In Transit, Received, Cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

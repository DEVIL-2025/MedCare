from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class ReplenishmentResponse(BaseModel):
    id: str
    priority: str
    sku: str
    name: Optional[str] = None
    warehouse: str
    current_stock: int
    recommended_qty: int
    recommended_frequency: str
    next_review_date: date
    decision_type: str
    preferred_source: str
    est_cost: str
    status: str
    requested_by: str
    reason_what: Optional[str] = None
    reason_why: Optional[str] = None
    reason_when: Optional[str] = None
    reason_impact: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: str
    supplier: str
    items_count: int = 1
    value: str
    status: str
    date: str
    sku: str
    product_name: Optional[str] = None
    warehouse: str
    qty: int
    eta: Optional[str] = None

    class Config:
        from_attributes = True

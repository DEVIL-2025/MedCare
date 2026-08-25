from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AlertResponse(BaseModel):
    id: str
    type: str
    category: str  # critical, warning, medium, info, good
    sku: Optional[str]
    product: Optional[str]
    warehouse: Optional[str]
    detail: str
    cause: Optional[str] = None
    recommended_action: Optional[str] = None
    status: str
    owner: str
    escalation_level: int
    is_escalated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertActionRequest(BaseModel):
    action: str  # acknowledge, progress, resolve, escalate
    notes: Optional[str] = None
    performed_by: Optional[str] = "Planner"

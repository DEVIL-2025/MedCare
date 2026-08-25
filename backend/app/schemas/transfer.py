from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TransferResponse(BaseModel):
    id: str
    sku: str
    name: Optional[str] = None
    from_wh: str
    to_wh: str
    available: int
    transfer: int
    savings: str
    reason: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransferExecuteRequest(BaseModel):
    transfer_id: str
    performed_by: Optional[str] = "Planner"

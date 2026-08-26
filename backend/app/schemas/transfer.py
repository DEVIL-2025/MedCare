from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class TransferExecuteRequest(BaseModel):
    transfer_id: str
    performed_by: Optional[str] = "Planner"

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class SupplierBase(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    lead_time_days: Optional[int] = 5
    category: Optional[str] = None
    status: Optional[str] = "Active"


class SupplierCreate(SupplierBase):
    id: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    lead_time_days: Optional[int] = None
    category: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierResponse(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: Optional[datetime] = None

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class TransactionCreate(BaseModel):
    transaction_type: str = Field(..., description="SALE, CONSUMPTION, RECEIPT, ADJUSTMENT, TRANSFER_OUT, TRANSFER_IN, TRANSFER")
    sku: str
    warehouse_id: str
    destination_warehouse_id: Optional[str] = None
    batch_id: Optional[str] = None
    quantity: int = Field(..., description="Units to transact (positive integer; engine handles deduction for sales)")
    reference_id: Optional[str] = None
    reason: Optional[str] = None
    performed_by: Optional[str] = "Planner"


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_type: str
    sku: str
    product_name: Optional[str] = None
    warehouse_id: str
    batch_id: Optional[str]
    quantity: int
    previous_stock: int
    new_stock: int
    reference_id: Optional[str]
    reason: Optional[str]
    performed_by: str
    timestamp: datetime

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    category: str = Field(..., min_length=2, max_length=80)
    criticality: Optional[str] = "Medium"
    unit: Optional[str] = "Units"
    shelf_life_days: Optional[int] = 730
    default_reorder_point: Optional[int] = 5000
    default_safety_stock: Optional[int] = 2500
    moq: Optional[int] = 1000
    unit_cost: Optional[float] = 50.0
    is_temperature_sensitive: Optional[bool] = False
    initial_warehouse_id: Optional[str] = None
    initial_stock: Optional[int] = 0


class ProductResponse(BaseModel):
    sku: str
    name: str
    category: str
    criticality: str
    unit: str
    shelf_life_days: int
    default_reorder_point: int
    default_safety_stock: int
    moq: int
    unit_cost: float
    is_temperature_sensitive: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    sku: str
    warehouse_id: str
    quantity: int = Field(..., gt=0)
    customer_name: str
    channel: Optional[str] = "Hospital"
    unit_price: Optional[float] = None
    reason: Optional[str] = None


class InventoryBase(BaseModel):
    sku: str
    warehouse_id: str
    current_stock: int
    reserved_stock: int = 0
    inbound_stock: int = 0
    reorder_point: int
    safety_stock: int
    status: str = "HEALTHY"
    risk_level: str = "low"
    days_of_cover: float = 30.0


class InventoryResponse(InventoryBase):
    id: int
    available_stock: int
    product_name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = "Units"
    unit_cost: Optional[float] = 50.0
    expiry: Optional[str] = "-"
    last_recalculated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchResponse(BaseModel):
    id: str
    sku: str
    warehouse_id: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    mfg_date: date
    expiry_date: date
    days_to_expiry: int
    status: str
    is_quarantined: bool

    class Config:
        from_attributes = True

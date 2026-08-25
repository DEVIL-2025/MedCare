from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class WarehouseCreate(BaseModel):
    id: str = Field(..., min_length=2, max_length=20)
    name: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=100)
    tier: Optional[str] = "Tier-2 DC"
    region: Optional[str] = "West"
    capacity_units: Optional[int] = 10000
    current_utilization_pct: Optional[float] = 50.0
    health_score: Optional[int] = 95
    status: Optional[str] = "Healthy"
    map_x: Optional[float] = 45.0
    map_y: Optional[float] = 50.0


class WarehouseResponse(BaseModel):
    id: str
    name: str
    location: str
    tier: str
    region: str
    capacity_units: int
    current_utilization_pct: float
    health_score: int
    status: str
    map_x: Optional[float] = 45.0
    map_y: Optional[float] = 50.0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

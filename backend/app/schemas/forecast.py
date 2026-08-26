from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime


class ForecastSummary(BaseModel):
    sku: str
    warehouse_id: str
    horizon_days: int
    avg_daily_demand_last_30d: int
    forecast_demand_next_30d: int
    predicted_peak_units: int
    predicted_peak_date: str
    forecast_confidence_pct: int
    trend_direction: str
    trend_description: str


class DemandSurgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    product_name: Optional[str]
    warehouse_id: str
    normal_demand: float
    recent_sensed_demand: float
    surge_pct: float
    severity: str
    status: str
    explanation: Optional[str]
    detected_at: datetime

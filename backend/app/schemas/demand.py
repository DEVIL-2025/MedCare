from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class DemandTrendPoint(BaseModel):
    date: str
    actual: Optional[int] = None
    forecast: Optional[int] = None
    upper: Optional[int] = None
    lower: Optional[int] = None


class DayOfWeekPoint(BaseModel):
    day: str
    units: int


class HeatmapRow(BaseModel):
    location: str
    values: List[int]


class DemandHeatmapResponse(BaseModel):
    weeks: List[str]
    rows: List[HeatmapRow]


class DemandDriver(BaseModel):
    label: str
    impact: str  # High, Medium, Low


class UpcomingEvent(BaseModel):
    event: str
    type: str
    start: str
    end: str
    impact: str
    skus: int
    expected: str

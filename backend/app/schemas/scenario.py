from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ScenarioRunRequest(BaseModel):
    name: Optional[str] = "What-If Scenario"
    demand_change_pct: Optional[float] = None
    demand_surge_pct: Optional[float] = None
    lead_time_change_days: Optional[int] = None
    lead_time_delay_days: Optional[int] = None
    starting_inventory_change_pct: float = 0.0
    capacity_constraint_pct: Optional[float] = None
    supply_reduction_pct: Optional[float] = None
    distributor_demand_change_pct: float = 0.0
    category_filter: Optional[str] = "All Categories"
    warehouse_filter: Optional[str] = None
    warehouse_id: Optional[str] = None

    def get_demand_change(self) -> float:
        if self.demand_change_pct is not None:
            return self.demand_change_pct
        if self.demand_surge_pct is not None:
            return self.demand_surge_pct
        return 20.0

    def get_lead_time_change(self) -> int:
        if self.lead_time_change_days is not None:
            return self.lead_time_change_days
        if self.lead_time_delay_days is not None:
            return self.lead_time_delay_days
        return 3

    def get_capacity_constraint(self) -> float:
        if self.capacity_constraint_pct is not None:
            return self.capacity_constraint_pct
        if self.supply_reduction_pct is not None:
            return self.supply_reduction_pct
        return 0.0

    def get_warehouse_filter(self) -> str:
        if self.warehouse_filter:
            return self.warehouse_filter
        if self.warehouse_id:
            return self.warehouse_id
        return "All Warehouses"


class ScenarioResponse(BaseModel):
    id: int
    name: str
    created_on: str
    demand_change: str
    lead_time_change: str
    stockout_value: str
    service_level: str
    status: str
    impact_summary: Dict[str, Any]
    impact_trend: List[Dict[str, Any]]
    affected_skus: List[Dict[str, Any]]
    comparison: List[Dict[str, Any]]

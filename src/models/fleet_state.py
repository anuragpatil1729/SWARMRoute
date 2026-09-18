from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.models.order import Order
from src.models.vehicle import Vehicle
from src.models.road import RoadNetwork, TrafficLevel


class ConnectivityState(str, Enum):
    CLOUD_MODE = "CLOUD_MODE"
    EDGE_MODE = "EDGE_MODE"
    MESH_MODE = "MESH_MODE"
    DISCONNECTED_MODE = "DISCONNECTED_MODE"


class FleetState(BaseModel):
    """
    Complete state representation of the logistics fleet at a specific instant in time.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: float = Field(default=0.0, ge=0.0, description="Current simulation or real timestamp")
    vehicles: Dict[str, Vehicle] = Field(default_factory=dict, description="Active vehicles indexed by vehicle_id")
    active_orders: Dict[str, Order] = Field(default_factory=dict, description="All active orders indexed by order_id")
    road_network: Optional[Any] = Field(default=None, description="RoadNetwork instance")
    traffic_state: Dict[str, TrafficLevel] = Field(default_factory=dict, description="Traffic state per road segment or zone")
    connectivity_state: ConnectivityState = Field(
        default=ConnectivityState.CLOUD_MODE, description="Current communication topology state"
    )
    weather_state: Optional[Any] = Field(default=None, description="Current weather condition or snapshot")


    def get_vehicle(self, vehicle_id: str) -> Optional[Vehicle]:
        return self.vehicles.get(vehicle_id)

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.active_orders.get(order_id)

    def get_unassigned_orders(self) -> List[Order]:
        return [o for o in self.active_orders.values() if o.assigned_vehicle_id is None]

    def total_fleet_capacity(self) -> float:
        return sum(v.max_weight for v in self.vehicles.values())

    def total_fleet_load(self) -> float:
        return sum(v.current_load for v in self.vehicles.values())

    def fleet_utilization(self) -> float:
        total_cap = self.total_fleet_capacity()
        if total_cap <= 0.0:
            return 0.0
        return (self.total_fleet_load() / total_cap) * 100.0

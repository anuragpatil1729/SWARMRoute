from __future__ import annotations
from enum import Enum
from typing import List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class VehicleStatus(str, Enum):
    IDLE = "IDLE"
    EN_ROUTE = "EN_ROUTE"
    DELIVERING = "DELIVERING"
    BROKEN_DOWN = "BROKEN_DOWN"
    CHARGING = "CHARGING"


class Vehicle(BaseModel):
    """
    Represents a truck in the heterogeneous fleet.
    """
    vehicle_id: str = Field(..., description="Unique vehicle identifier")
    vehicle_type: str = Field(default="heavy_duty", description="Classification: heavy_duty, medium_duty, light, ev")
    max_weight: float = Field(..., gt=0.0, description="Maximum payload weight capacity")
    max_volume: float = Field(default=50.0, gt=0.0, description="Maximum volume capacity in m^3")
    current_location: Tuple[float, float] = Field(default=(0.0, 0.0), description="Current position coordinates")
    current_load: float = Field(default=0.0, ge=0.0, description="Current loaded weight")
    current_volume_load: float = Field(default=0.0, ge=0.0, description="Current loaded volume")
    fuel_level: float = Field(default=100.0, ge=0.0, description="Current fuel remaining (Liters or %)")
    fuel_capacity: float = Field(default=300.0, gt=0.0, description="Total fuel tank capacity (Liters)")
    fuel_efficiency: float = Field(default=30.0, gt=0.0, description="Base fuel efficiency (L/100km at empty)")
    average_speed: float = Field(default=40.0, gt=0.0, description="Nominal cruise speed (km/h)")
    status: VehicleStatus = Field(default=VehicleStatus.IDLE, description="Current operational status")
    current_route: List[Union[int, str]] = Field(default_factory=list, description="Sequence of stop/node identifiers")
    assigned_orders: List[str] = Field(default_factory=list, description="Order IDs assigned to this vehicle")

    def remaining_weight_capacity(self) -> float:
        """Returns remaining available weight capacity."""
        return max(0.0, self.max_weight - self.current_load)

    def remaining_volume_capacity(self) -> float:
        """Returns remaining available volume capacity."""
        return max(0.0, self.max_volume - self.current_volume_load)

    def can_load(self, weight: float, volume: float = 0.0) -> bool:
        """Checks if vehicle can accommodate additional weight and volume without violation."""
        return (self.current_load + weight <= self.max_weight + 1e-6) and (
            self.current_volume_load + volume <= self.max_volume + 1e-6
        )

    def load_order(self, order_id: str, weight: float, volume: float = 0.0) -> bool:
        """Attempts to load an order onto the vehicle."""
        if not self.can_load(weight, volume):
            return False
        self.assigned_orders.append(order_id)
        self.current_load += weight
        self.current_volume_load += volume
        return True

    def reset_load(self) -> None:
        """Resets load and assignments."""
        self.current_load = 0.0
        self.current_volume_load = 0.0
        self.assigned_orders.clear()
        self.current_route.clear()
        self.status = VehicleStatus.IDLE

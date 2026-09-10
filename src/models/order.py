from __future__ import annotations
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    LOADED = "LOADED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    DELIVERED = "DELIVERED"
    LATE = "LATE"
    FAILED = "FAILED"
    REASSIGNED = "REASSIGNED"


class Order(BaseModel):
    """
    Represents a customer order in the logistics network.
    Coordinates can be (x, y) coordinates or (latitude, longitude).
    Time values are modeled in consistent units (e.g. minutes or hours from start of shift).
    """
    order_id: str = Field(..., description="Unique order identifier")
    pickup_location: Tuple[float, float] = Field(
        default=(0.0, 0.0), description="Coordinates of pickup location (x, y)"
    )
    destination: Tuple[float, float] = Field(
        ..., description="Coordinates of destination/delivery location (x, y)"
    )
    demand_weight: float = Field(..., ge=0.0, description="Order weight demand (kg or units)")
    volume: float = Field(default=0.0, ge=0.0, description="Order volume demand (m^3)")
    priority: int = Field(default=1, ge=1, le=5, description="Priority level: 1 (normal) to 5 (critical/urgent)")
    earliest_delivery: float = Field(
        default=0.0, ge=0.0, description="Start of delivery time window (ready time)"
    )
    latest_delivery: float = Field(
        ..., ge=0.0, description="End of delivery time window (due date)"
    )
    service_time: float = Field(
        default=0.0, ge=0.0, description="Duration required to unload/service at destination"
    )
    release_time: float = Field(
        default=0.0, ge=0.0, description="Timestamp when order becomes available to system"
    )
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current lifecycle status")
    assigned_vehicle_id: Optional[str] = Field(default=None, description="Vehicle ID currently assigned")
    actual_arrival_time: Optional[float] = Field(default=None, description="Recorded arrival time at customer")
    actual_delivery_time: Optional[float] = Field(default=None, description="Recorded completed delivery time")

    @field_validator("latest_delivery")
    @classmethod
    def validate_time_window(cls, v: float, info) -> float:
        earliest = info.data.get("earliest_delivery", 0.0)
        if v < earliest:
            raise ValueError(f"latest_delivery ({v}) must be >= earliest_delivery ({earliest})")
        return v

    def is_late(self, arrival_time: Optional[float] = None) -> bool:
        """Returns True if arrival exceeds latest delivery deadline."""
        if arrival_time is not None:
            return arrival_time > self.latest_delivery
        if self.status == OrderStatus.LATE:
            return True
        t = self.actual_arrival_time if self.actual_arrival_time is not None else self.actual_delivery_time
        return t > self.latest_delivery if t is not None else False

    def lateness(self, arrival_time: Optional[float] = None) -> float:
        """Returns lateness duration beyond deadline (0.0 if on time)."""
        if arrival_time is not None:
            return max(0.0, arrival_time - self.latest_delivery)
        t = self.actual_arrival_time if self.actual_arrival_time is not None else self.actual_delivery_time
        return max(0.0, t - self.latest_delivery) if t is not None else 0.0

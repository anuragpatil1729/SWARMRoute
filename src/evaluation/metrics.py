from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FleetMetrics(BaseModel):
    """
    Standardized benchmark metrics container.
    """
    system_name: str = Field(..., description="Name of the system or algorithm evaluated")
    dataset_name: str = Field(default="Solomon C101", description="Dataset or scenario name")
    num_vehicles_used: int = Field(default=0, description="Active trucks deployed")
    total_vehicles_available: int = Field(default=0, description="Total fleet size")
    total_orders: int = Field(default=0, description="Total order count evaluated")
    delivered_orders: int = Field(default=0, description="Successfully scheduled orders")
    total_distance_km: float = Field(default=0.0, description="Total route distance (km)")
    total_travel_time_hrs: float = Field(default=0.0, description="Total travel time")
    total_fuel_liters: float = Field(default=0.0, description="Total diesel consumed (L)")
    total_co2_kg: float = Field(default=0.0, description="Total CO2 emissions (kg)")
    late_deliveries: int = Field(default=0, description="Number of orders served late")
    max_lateness: float = Field(default=0.0, description="Max lateness across orders")
    vehicle_utilization_pct: float = Field(default=0.0, description="Average payload capacity utilization")
    total_cost: float = Field(default=0.0, description="Aggregated multi-objective cost")
    runtime_seconds: float = Field(default=0.0, description="Algorithm computation runtime")

    def format_summary(self, currency_symbol: str = "₹") -> str:
        """Returns clean formatted text block matching prompt specifications."""
        return (
            f"Distance: {self.total_distance_km:,.2f} km\n"
            f"Fuel: {self.total_fuel_liters:,.2f} L\n"
            f"CO2: {self.total_co2_kg:,.2f} kg\n"
            f"Vehicles Used: {self.num_vehicles_used} / {self.total_vehicles_available}\n"
            f"Fleet Utilization: {self.vehicle_utilization_pct:.1f} %\n"
            f"Late deliveries: {self.late_deliveries}\n"
            f"Max lateness: {self.max_lateness:.1f}\n"
            f"Cost: {currency_symbol}{self.total_cost:,.2f}\n"
            f"Runtime: {self.runtime_seconds:.3f} sec"
        )

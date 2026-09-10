from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, TrafficLevel
from src.models.fleet_state import FleetState, ConnectivityState
from src.prediction.fuel import FuelModel, DeterministicFuelModel
from src.simulation.traffic import TrafficSimulator
from src.simulation.events import EventEngine, FleetEvent, EventType
from src.networking.mesh import MeshNetwork
from src.networking.connectivity import ConnectivityManager
from src.networking.messages import MeshMessage, MessageType
from src.optimization.dynamic_reoptimizer import DynamicReoptimizer


class SimulationSnapshot(BaseModel):
    """Timestamped snapshot of ongoing fleet simulation."""
    current_time_mins: float
    connectivity_mode: ConnectivityState
    active_vehicles_count: int
    broken_vehicles_count: int
    delivered_orders_count: int
    late_orders_count: int
    total_fuel_liters: float
    total_co2_kg: float


class FleetSimulationEnvironment:
    """
    Complete Discrete-Event Simulation Environment for Autonomous Logistics Fleets.
    Coordinates spatial movement, traffic evolution, stochastic disruptions,
    mesh communication, and local self-healing.
    """

    def __init__(
        self,
        fleet_state: FleetState,
        road_network: RoadNetwork,
        node_id_map: Dict[str, int],
        fuel_model: Optional[FuelModel] = None,
        traffic_sim: Optional[TrafficSimulator] = None,
        mesh_network: Optional[MeshNetwork] = None,
        time_step_mins: float = 5.0,
        seed: int = 42,
    ) -> None:
        self.fleet_state = fleet_state
        self.road_network = road_network
        self.node_id_map = node_id_map
        self.reverse_node_map = {v: k for k, v in node_id_map.items()}
        self.fuel_model = fuel_model or DeterministicFuelModel()
        self.traffic_sim = traffic_sim or TrafficSimulator(seed=seed)
        self.mesh_network = mesh_network or MeshNetwork(seed=seed)
        self.conn_manager = ConnectivityManager(initial_state=fleet_state.connectivity_state)
        self.reoptimizer = DynamicReoptimizer(fuel_model=self.fuel_model)
        self.event_engine = EventEngine()

        self.current_time_mins = 0.0
        self.time_step_mins = time_step_mins
        self.delivered_orders: Set[str] = set()
        self.late_orders: Set[str] = set()
        self.cumulative_fuel = 0.0
        self.cumulative_co2 = 0.0

        # Register truck positions in mesh network
        for v_id, v in self.fleet_state.vehicles.items():
            self.mesh_network.update_node_position(v_id, v.current_location)

    def schedule_disruption(
        self,
        time_mins: float,
        breakdown_vehicle_id: Optional[str] = None,
        traffic_spike_edge: Optional[Tuple[int, int]] = None,
        disconnect_cloud: bool = True,
        urgent_orders: Optional[List[Order]] = None,
    ) -> None:
        """Schedules simultaneous multi-incident disruption at time T."""
        if disconnect_cloud:
            self.event_engine.schedule(
                FleetEvent(
                    event_id="EV_CONN_LOSS",
                    event_type=EventType.CONNECTIVITY_LOSS,
                    timestamp=time_mins,
                    payload={"target_mode": ConnectivityState.MESH_MODE},
                    description="Central Internet / 4G cellular blackout",
                )
            )

        if breakdown_vehicle_id:
            self.event_engine.schedule(
                FleetEvent(
                    event_id=f"EV_BRK_{breakdown_vehicle_id}",
                    event_type=EventType.VEHICLE_BREAKDOWN,
                    timestamp=time_mins,
                    payload={"vehicle_id": breakdown_vehicle_id},
                    description=f"{breakdown_vehicle_id} mechanical breakdown on route",
                )
            )

        if traffic_spike_edge:
            self.event_engine.schedule(
                FleetEvent(
                    event_id="EV_TRAF_SPIKE",
                    event_type=EventType.TRAFFIC_CHANGE,
                    timestamp=time_mins,
                    payload={"edge": traffic_spike_edge, "level": TrafficLevel.SEVERE},
                    description="Severe traffic congestion spike on key road segment",
                )
            )

        if urgent_orders:
            for idx, uo in enumerate(urgent_orders):
                self.event_engine.schedule(
                    FleetEvent(
                        event_id=f"EV_URG_{idx:02d}",
                        event_type=EventType.URGENT_ORDER,
                        timestamp=time_mins,
                        payload={"order": uo},
                        description=f"Urgent customer order {uo.order_id}",
                    )
                )

    def step(self) -> List[FleetEvent]:
        """Advances simulation by time_step_mins."""
        self.current_time_mins += self.time_step_mins

        # 1. Update traffic in road network
        self.traffic_sim.update_road_network(self.road_network, self.current_time_mins)

        # 2. Pop and apply due events
        due_events = self.event_engine.pop_due_events(self.current_time_mins)
        for ev in due_events:
            self.event_engine.apply_event(ev, self.fleet_state)
            if ev.event_type == EventType.CONNECTIVITY_LOSS:
                self.conn_manager.on_cloud_lost()
            elif ev.event_type == EventType.VEHICLE_BREAKDOWN:
                v_id = ev.payload.get("vehicle_id")
                if v_id:
                    self.mesh_network.set_node_failed(v_id, failed=True)

        # 3. Update truck positions on mesh
        for v_id, v in self.fleet_state.vehicles.items():
            self.mesh_network.update_node_position(v_id, v.current_location)

        return due_events

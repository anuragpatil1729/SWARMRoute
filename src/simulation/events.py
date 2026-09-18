from __future__ import annotations
import heapq
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, RoadStatus, TrafficLevel
from src.models.fleet_state import FleetState, ConnectivityState


class EventType(str, Enum):
    NEW_ORDER = "NEW_ORDER"
    URGENT_ORDER = "URGENT_ORDER"
    TRAFFIC_CHANGE = "TRAFFIC_CHANGE"
    ROAD_CLOSURE = "ROAD_CLOSURE"
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    FUEL_LOW = "FUEL_LOW"
    DELIVERY_DELAY = "DELIVERY_DELAY"
    CONNECTIVITY_LOSS = "CONNECTIVITY_LOSS"
    CONNECTIVITY_RESTORED = "CONNECTIVITY_RESTORED"
    MESH_LINK_FAILURE = "MESH_LINK_FAILURE"
    MESH_LINK_RESTORED = "MESH_LINK_RESTORED"
    WEATHER = "WEATHER"



class FleetEvent(BaseModel):
    """
    Standardized dynamic event modifying the state of the logistics fleet.
    """
    event_id: str
    event_type: EventType
    timestamp: float = Field(..., ge=0.0, description="Timestamp (in minutes) when the event fires")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific payload attributes")
    description: str = Field(default="", description="Human-readable event explanation")
    handled: bool = False

    def __lt__(self, other: FleetEvent) -> bool:
        return self.timestamp < other.timestamp


class EventEngine:
    """
    Dynamic Event Dispatcher.
    Maintains a priority queue of scheduled events and mutates FleetState upon trigger.
    """

    def __init__(self) -> None:
        self.event_queue: List[Tuple[float, int, FleetEvent]] = []
        self.history: List[FleetEvent] = []
        self.counter = 0

    def schedule(self, event: FleetEvent) -> None:
        self.counter += 1
        heapq.heappush(self.event_queue, (event.timestamp, self.counter, event))

    def pop_due_events(self, current_time_mins: float) -> List[FleetEvent]:
        due = []
        while self.event_queue and self.event_queue[0][0] <= current_time_mins:
            _, _, ev = heapq.heappop(self.event_queue)
            due.append(ev)
        return due

    def apply_event(self, event: FleetEvent, fleet_state: FleetState) -> FleetState:
        """Applies event consequences to the live FleetState."""
        fleet_state.timestamp = event.timestamp
        event_type = event.event_type
        payload = event.payload

        if event_type in (EventType.NEW_ORDER, EventType.URGENT_ORDER):
            order_data = payload.get("order")
            if isinstance(order_data, Order):
                fleet_state.active_orders[order_data.order_id] = order_data
            elif isinstance(order_data, dict):
                order_obj = Order(**order_data)
                fleet_state.active_orders[order_obj.order_id] = order_obj

        elif event_type == EventType.VEHICLE_BREAKDOWN:
            v_id = payload.get("vehicle_id")
            if v_id and v_id in fleet_state.vehicles:
                veh = fleet_state.vehicles[v_id]
                veh.status = VehicleStatus.BROKEN_DOWN

        elif event_type == EventType.CONNECTIVITY_LOSS:
            # Drop from cloud to mesh or edge mode
            target_mode = payload.get("target_mode", ConnectivityState.MESH_MODE)
            fleet_state.connectivity_state = ConnectivityState(target_mode)

        elif event_type == EventType.CONNECTIVITY_RESTORED:
            fleet_state.connectivity_state = ConnectivityState.CLOUD_MODE

        elif event_type == EventType.TRAFFIC_CHANGE:
            zone = payload.get("zone")
            level = payload.get("level", TrafficLevel.HEAVY)
            if zone:
                fleet_state.traffic_state[str(zone)] = TrafficLevel(level)

        elif event_type == EventType.ROAD_CLOSURE:
            edge = payload.get("edge")
            if edge and fleet_state.road_network:
                u, v = edge
                if fleet_state.road_network.graph.has_edge(u, v):
                    fleet_state.road_network.graph[u][v]["status"] = RoadStatus.CLOSED
                    fleet_state.road_network.graph[u][v]["speed"] = 0.0

        elif event_type == EventType.FUEL_LOW:
            v_id = payload.get("vehicle_id")
            fuel = payload.get("fuel_level", 10.0)
            if v_id and v_id in fleet_state.vehicles:
                fleet_state.vehicles[v_id].fuel_level = fuel

        elif event_type == EventType.DELIVERY_DELAY:
            order_id = payload.get("order_id")
            delay = payload.get("delay_mins", 15.0)
            if order_id and order_id in fleet_state.active_orders:
                fleet_state.active_orders[order_id].service_time += delay

        elif event_type in (EventType.MESH_LINK_FAILURE, EventType.MESH_LINK_RESTORED):
            # Tracked in payload for mesh network synchronization
            pass

        elif event_type == EventType.WEATHER:
            # Weather condition or snapshot recorded on fleet state
            fleet_state.weather_state = payload.get("weather") or payload.get("snapshot") or payload


        event.handled = True
        self.history.append(event)
        return fleet_state

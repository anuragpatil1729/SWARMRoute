from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.fleet_state import ConnectivityState
from src.networking.messages import MeshMessage, MessageType


class LocalAgentState(BaseModel):
    """
    Isolated local memory and situational awareness of a single truck edge unit.
    STRICTLY isolated from global fleet state when in MESH_MODE.
    """
    vehicle_id: str
    current_location: Tuple[float, float] = (0.0, 0.0)
    current_node: int = 0
    next_node: Optional[int] = None
    current_route: List[int] = Field(default_factory=list)
    assigned_orders: List[str] = Field(default_factory=list)
    current_load: float = 0.0
    max_weight: float = 200.0
    fuel_level: float = 100.0
    status: VehicleStatus = VehicleStatus.IDLE
    connectivity: ConnectivityState = ConnectivityState.CLOUD_MODE
    known_neighbors: Dict[str, Tuple[float, float]] = Field(default_factory=dict)
    known_orders: Dict[str, Order] = Field(default_factory=dict)
    accepted_transfers: List[str] = Field(default_factory=list)
    sent_messages_count: int = 0
    received_messages_count: int = 0


class TruckAgent:
    """
    Autonomous Edge Agent running inside a vehicle.
    Capable of local decision making, mesh communication, and peer load exchange.
    """

    def __init__(
        self,
        vehicle_id: str,
        initial_vehicle: Vehicle,
        initial_orders: Optional[Dict[str, Order]] = None,
        max_detour_km: float = 25.0,
    ) -> None:
        self.vehicle_id = vehicle_id
        self.max_detour_km = max_detour_km
        self.state = LocalAgentState(
            vehicle_id=vehicle_id,
            current_location=initial_vehicle.current_location,
            current_node=initial_vehicle.current_node or 0,
            next_node=initial_vehicle.next_node,
            current_route=[int(n) for n in initial_vehicle.current_route if isinstance(n, (int, str)) and str(n).isdigit()],
            assigned_orders=list(initial_vehicle.assigned_orders),
            current_load=initial_vehicle.current_load,
            max_weight=initial_vehicle.max_weight,
            fuel_level=initial_vehicle.fuel_level,
            status=initial_vehicle.status,
            known_orders=dict(initial_orders or {}),
        )
        self.outbox: List[MeshMessage] = []

    def remaining_capacity(self) -> float:
        return max(0.0, self.state.max_weight - self.state.current_load)

    def can_absorb(self, order: Order) -> bool:
        if self.state.status == VehicleStatus.BROKEN_DOWN:
            return False
        return (self.state.current_load + order.demand_weight) <= (self.state.max_weight + 1e-6)

    def evaluate_order_absorption(
        self,
        order: Order,
        order_node_idx: int,
        node_coords: Dict[int, Tuple[float, float]],
    ) -> Tuple[bool, float, int]:
        """
        Evaluates best insertion position and detour cost for absorbing an order into current_route.
        Returns (is_feasible, min_detour_km, best_insert_index).
        """
        if not self.can_absorb(order):
            return False, float("inf"), -1

        route = self.state.current_route
        if len(route) < 2:
            return True, 0.0, len(route)

        dest_coord = node_coords.get(order_node_idx, order.destination)
        best_detour = float("inf")
        best_idx = -1

        # Search for cheapest insertion index
        for i in range(len(route) - 1):
            u_node = route[i]
            v_node = route[i + 1]
            u_coord = node_coords.get(u_node, (0.0, 0.0))
            v_coord = node_coords.get(v_node, (0.0, 0.0))

            direct_dist = math.hypot(u_coord[0] - v_coord[0], u_coord[1] - v_coord[1])
            detour_dist = (
                math.hypot(u_coord[0] - dest_coord[0], u_coord[1] - dest_coord[1])
                + math.hypot(dest_coord[0] - v_coord[0], dest_coord[1] - v_coord[1])
            )
            added_dist = max(0.0, detour_dist - direct_dist)

            if added_dist < best_detour:
                best_detour = added_dist
                best_idx = i + 1

        if best_detour <= self.max_detour_km:
            return True, round(best_detour, 2), best_idx
        return False, best_detour, -1

    def receive_message(
        self,
        message: MeshMessage,
        node_coords: Dict[int, Tuple[float, float]],
    ) -> Optional[MeshMessage]:
        """
        Processes an incoming mesh message locally using only local information.
        """
        self.state.received_messages_count += 1
        m_type = message.message_type

        # 1. Peer breakdown broadcast
        if m_type in (MessageType.BREAKDOWN_ALERT, MessageType.SOS_BREAKDOWN):
            broken_v_id = message.sender_id
            if broken_v_id == self.vehicle_id:
                return None  # Own message

            stranded_orders_data = message.payload.get("orders", [])
            for o_data in stranded_orders_data:
                order = Order(**o_data) if isinstance(o_data, dict) else o_data
                order_node = message.payload.get("order_nodes", {}).get(order.order_id, 0)
                feasible, detour, insert_idx = self.evaluate_order_absorption(order, order_node, node_coords)

                if feasible:
                    # Respond with acceptance bid
                    accept_msg = MeshMessage(
                        message_id=f"ACCEPT_{self.vehicle_id}_{order.order_id}",
                        message_type=MessageType.ORDER_TRANSFER_ACCEPT,
                        sender_id=self.vehicle_id,
                        receiver_id=broken_v_id,
                        timestamp_mins=message.timestamp_mins + 0.1,
                        payload={
                            "order_id": order.order_id,
                            "order": order.model_dump(),
                            "order_node": order_node,
                            "detour_km": detour,
                            "insert_index": insert_idx,
                            "capacity_remaining": self.remaining_capacity() - order.demand_weight,
                        },
                    )
                    self.outbox.append(accept_msg)
                    return accept_msg

        # 2. Transfer proposal or confirmation
        elif m_type == MessageType.ORDER_TRANSFER_ACCEPT:
            # Confirmed transfer assignment
            target_veh = message.payload.get("target_vehicle_id")
            if target_veh == self.vehicle_id:
                order_id = message.payload.get("order_id")
                order_node = message.payload.get("order_node")
                insert_idx = message.payload.get("insert_index")
                order_data = message.payload.get("order")

                if order_id and order_node is not None:
                    if order_id not in self.state.assigned_orders:
                        self.state.assigned_orders.append(order_id)
                        if order_data:
                            self.state.known_orders[order_id] = Order(**order_data) if isinstance(order_data, dict) else order_data
                            self.state.current_load += self.state.known_orders[order_id].demand_weight

                        if insert_idx is not None and 0 <= insert_idx <= len(self.state.current_route):
                            self.state.current_route.insert(insert_idx, order_node)
                        else:
                            # Insert before depot return
                            if len(self.state.current_route) > 1:
                                self.state.current_route.insert(-1, order_node)
                            else:
                                self.state.current_route.append(order_node)
                        self.state.accepted_transfers.append(order_id)

        # 3. Traffic Alert
        elif m_type == MessageType.TRAFFIC_ALERT:
            # Edge congestion report received from peer
            edge = message.payload.get("edge")
            level = message.payload.get("level")
            # Truck registers congestion observation locally
            pass

        return None

    def trigger_breakdown(self, current_time_mins: float, node_id_map: Dict[str, int]) -> MeshMessage:
        """
        Marks this truck broken down and broadcasts an SOS_BREAKDOWN mesh message.
        """
        self.state.status = VehicleStatus.BROKEN_DOWN
        remaining = [
            self.state.known_orders[oid]
            for oid in self.state.assigned_orders
            if oid in self.state.known_orders
        ]
        order_nodes = {o.order_id: node_id_map.get(o.order_id, 0) for o in remaining}

        sos_msg = MeshMessage(
            message_id=f"SOS_{self.vehicle_id}_{int(current_time_mins)}",
            message_type=MessageType.BREAKDOWN_ALERT,
            sender_id=self.vehicle_id,
            receiver_id="BROADCAST",
            timestamp_mins=current_time_mins,
            payload={
                "vehicle_id": self.vehicle_id,
                "location": self.state.current_location,
                "orders": [o.model_dump() for o in remaining],
                "order_nodes": order_nodes,
            },
        )
        self.outbox.append(sos_msg)
        self.state.sent_messages_count += 1
        return sos_msg

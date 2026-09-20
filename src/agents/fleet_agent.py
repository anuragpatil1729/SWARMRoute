from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState, ConnectivityState
from src.agents.truck_agent import TruckAgent
from src.networking.mesh import MeshNetwork
from src.networking.messages import MeshMessage, MessageType
from src.optimization.delivery_exchange import DeliveryExchangeEngine, TransferAction, DeliveryExchangePlan


def select_winning_bid(
    bids: List[Dict[str, Any]],
    order_id: str,
    truck_agents: Optional[Dict[str, Any]] = None,
    max_detour_km: float = 25.0,
) -> Optional[Dict[str, Any]]:
    """
    Selects the winning bid for a stranded order strictly adhering to deterministic contract-net protocol:
    1. Feasible bidders only:
       - Must match order_id
       - Must contain valid bidder_vehicle_id from an eligible operational vehicle
       - Bidder vehicle must NOT be broken down (status != BROKEN_DOWN)
       - Bidder vehicle must NOT be disconnected (connectivity != DISCONNECTED_MODE)
       - Must have sufficient capacity (capacity_remaining >= 0.0)
       - Must have detour_km within max_detour_km
       - Must have non-negative finite additional_fuel and additional_co2
    2. Primary ranking: Minimum detour_km
    3. Secondary ranking: Minimum additional_fuel
    4. Tertiary ranking: Minimum additional_co2
    5. Deterministic tie-break: Lexicographically smallest vehicle_id
    
    Returns winning bid payload dict, or None if no feasible bid exists.
    """
    feasible_bids: List[Dict[str, Any]] = []

    for b in bids:
        if not isinstance(b, dict):
            continue
        if b.get("order_id") != order_id:
            continue

        bidder_id = b.get("bidder_vehicle_id")
        if not bidder_id or not isinstance(bidder_id, str):
            continue

        # Check vehicle status and connectivity if agents dictionary provided
        if truck_agents is not None:
            if bidder_id not in truck_agents:
                continue
            agent = truck_agents[bidder_id]
            st = getattr(agent, "state", None)
            v_status = getattr(st, "status", getattr(agent, "status", None))
            if v_status == VehicleStatus.BROKEN_DOWN:
                continue
            v_conn = getattr(st, "connectivity", None)
            if v_conn == ConnectivityState.DISCONNECTED_MODE:
                continue

        # Capacity constraint check
        cap_rem = float(b.get("capacity_remaining", 0.0))
        if cap_rem < -1e-5:
            continue

        # Feasibility check on detour
        detour = float(b.get("detour_km", float("inf")))
        if math.isinf(detour) or math.isnan(detour) or detour > max_detour_km or detour < 0.0:
            continue

        # Non-negative fuel and CO2 checks
        add_fuel = float(b.get("additional_fuel", float("inf")))
        add_co2 = float(b.get("additional_co2", float("inf")))
        if math.isinf(add_fuel) or math.isnan(add_fuel) or add_fuel < 0.0:
            continue
        if math.isinf(add_co2) or math.isnan(add_co2) or add_co2 < 0.0:
            continue

        feasible_bids.append(b)

    if not feasible_bids:
        return None

    # Deterministic multi-criteria sorting:
    # 1. minimum detour_km
    # 2. minimum additional_fuel
    # 3. minimum additional_co2
    # 4. lexicographically smallest vehicle_id as final tie-break
    feasible_bids.sort(
        key=lambda b: (
            float(b.get("detour_km", float("inf"))),
            float(b.get("additional_fuel", float("inf"))),
            float(b.get("additional_co2", float("inf"))),
            str(b.get("bidder_vehicle_id", "")),
        )
    )

    return feasible_bids[0]


class FleetAgent:
    """
    Decentralized Fleet Coordinator.
    Oversees autonomous truck agents and coordinates peer-to-peer load exchange
    over the simulated wireless mesh network when disconnected from the cloud.
    """

    def __init__(
        self,
        fleet_state: FleetState,
        road_network: RoadNetwork,
        mesh_network: Optional[MeshNetwork] = None,
        max_detour_km: float = 25.0,
        seed: int = 42,
        fuel_predictor: Optional[Any] = None,
        use_ml_fuel: bool = False,
    ) -> None:
        self.fleet_state = fleet_state
        self.road_network = road_network
        self.mesh_network = mesh_network or MeshNetwork(seed=seed)
        self.exchange_engine = DeliveryExchangeEngine(max_detour_km=max_detour_km)
        self.truck_agents: Dict[str, TruckAgent] = {}
        self.total_mesh_messages: int = 0
        self.total_mesh_hops: int = 0
        self.recovered_orders_count: int = 0
        self.fuel_predictor = fuel_predictor
        self.use_ml_fuel = use_ml_fuel

        # Initialize local edge agent on each vehicle and register on mesh
        for v_id, vehicle in fleet_state.vehicles.items():
            self.truck_agents[v_id] = TruckAgent(
                vehicle_id=v_id,
                initial_vehicle=vehicle,
                initial_orders=fleet_state.active_orders,
                max_detour_km=max_detour_km,
                fuel_predictor=fuel_predictor,
                use_ml_fuel=use_ml_fuel,
            )
            self.mesh_network.update_node_position(v_id, vehicle.current_location)

    def on_vehicle_breakdown_decentralized(
        self,
        failed_vehicle_id: str,
        current_time_mins: float,
        node_id_map: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Coordinates decentralized self-healing over the mesh network:
        1. Failed truck creates and broadcasts BREAKDOWN_ALERT over mesh.
        2. Neighboring reachable trucks receive alert and evaluate spare capacity.
        3. Interested candidate trucks reply with ORDER_TRANSFER_ACCEPT bids.
        4. Lowest-detour feasible assignment is selected deterministically and confirmed via mesh.
        5. Local routes and loads are updated atomically without central cloud access.
        """
        # Ensure all dynamic partner vehicles in fleet_state have corresponding edge truck_agents
        for vehicle_id, vehicle in self.fleet_state.vehicles.items():
            if vehicle_id not in self.truck_agents:
                self.truck_agents[vehicle_id] = TruckAgent(
                    vehicle_id=vehicle_id,
                    initial_vehicle=vehicle,
                    initial_orders=self.fleet_state.active_orders,
                    max_detour_km=self.exchange_engine.max_detour_km,
                    fuel_predictor=self.fuel_predictor,
                    use_ml_fuel=self.use_ml_fuel,
                )

        if failed_vehicle_id not in self.truck_agents:
            return {"success": False, "reason": f"Unknown vehicle: {failed_vehicle_id}"}

        # Refresh edge-agent local state from the physical simulator immediately
        # before the auction.  This keeps capacity, route and location bids
        # grounded in the current simulation tick rather than construction-time
        # snapshots.
        for vehicle_id, vehicle in self.fleet_state.vehicles.items():
            agent = self.truck_agents[vehicle_id]
            agent.state.current_location = vehicle.current_location
            agent.state.current_node = vehicle.current_node or 0
            agent.state.next_node = vehicle.next_node
            agent.state.current_route = list(vehicle.current_route)
            agent.state.assigned_orders = list(vehicle.assigned_orders)
            agent.state.current_load = vehicle.current_load
            agent.state.status = vehicle.status
            agent.state.connectivity = self.fleet_state.connectivity_state
            self.mesh_network.update_node_position(vehicle_id, vehicle.current_location)

        broken_agent = self.truck_agents[failed_vehicle_id]
        sos_msg = broken_agent.trigger_breakdown(current_time_mins, node_id_map)
        self.total_mesh_messages += 1

        # Broadcast across mesh network
        delivered_broadcast = self.mesh_network.transmit(sos_msg)
        self.total_mesh_hops += max(1, sos_msg.hop_count)

        # Collect candidate bids from all operational peer trucks in the mesh
        bids: List[Dict[str, Any]] = []
        node_coords = self.road_network.node_coordinates

        for v_id, peer_agent in self.truck_agents.items():
            if v_id == failed_vehicle_id or peer_agent.state.status == VehicleStatus.BROKEN_DOWN:
                continue

            # In MESH_MODE, verify peer is reachable in mesh topology
            import networkx as nx
            topo = self.mesh_network.topology
            if not (topo.has_node(failed_vehicle_id) and topo.has_node(v_id) and nx.has_path(topo, failed_vehicle_id, v_id)):
                continue

            # Transmit SOS message to peer over physical mesh
            sos_to_peer = sos_msg.model_copy(deep=True)
            sos_to_peer.receiver_id = v_id
            if not self.mesh_network.transmit(sos_to_peer):
                continue

            if hasattr(peer_agent, "generate_bids_for_breakdown"):
                peer_bids = peer_agent.generate_bids_for_breakdown(sos_to_peer, node_coords)
            else:
                msg = peer_agent.receive_message(sos_to_peer, node_coords)
                peer_bids = [msg] if msg else []

            for bid_msg in peer_bids:
                if bid_msg and bid_msg.payload:
                    if self.mesh_network.transmit(bid_msg):
                        self.total_mesh_messages += 1
                        bids.append(bid_msg.payload)

        # Reassign orders using deterministic contract-net winner selection:
        assigned_transfers = []
        remaining_order_ids = list(broken_agent.state.assigned_orders)

        for oid in remaining_order_ids:
            winner = select_winning_bid(
                bids=bids,
                order_id=oid,
                truck_agents=self.truck_agents,
                max_detour_km=self.exchange_engine.max_detour_km,
            )
            if not winner:
                continue

            bidder_id = winner["bidder_vehicle_id"]

            confirm_msg = MeshMessage(
                message_id=f"CONFIRM_{oid}_{bidder_id}",
                message_type=MessageType.ORDER_TRANSFER_ACCEPT,
                sender_id=failed_vehicle_id,
                receiver_id=bidder_id,
                timestamp_mins=current_time_mins + 0.2,
                payload={
                    "target_vehicle_id": bidder_id,
                    "order_id": oid,
                    "order": winner.get("order"),
                    "order_node": winner.get("order_node"),
                    "insert_index": winner.get("insert_index"),
                },
            )
            if not self.mesh_network.transmit(confirm_msg):
                continue
            self.total_mesh_messages += 1
            self.total_mesh_hops += max(1, confirm_msg.hop_count)

            # Winning agent applies transfer locally
            self.truck_agents[bidder_id].receive_message(confirm_msg, node_coords)
            self.recovered_orders_count += 1
            assigned_transfers.append({
                "order_id": oid,
                "from_vehicle": failed_vehicle_id,
                "to_vehicle": bidder_id,
                "target_vehicle_id": bidder_id,
                "detour_km": winner.get("detour_km"),
                "additional_fuel": winner.get("additional_fuel"),
                "additional_co2": winner.get("additional_co2"),
                "order_node": winner.get("order_node"),
                "insert_index": winner.get("insert_index"),
            })

        # Atomically remove transferred orders and route nodes from failed agent
        broken_agent.state.assigned_orders = [
            oid for oid in broken_agent.state.assigned_orders
            if not any(t["order_id"] == oid for t in assigned_transfers)
        ]
        transferred_nodes = {
            t["order_node"] for t in assigned_transfers if t.get("order_node") is not None
        }
        broken_agent.state.current_route = [
            n for n in broken_agent.state.current_route if n not in transferred_nodes
        ]
        transferred_weight = sum(
            self.fleet_state.active_orders[t["order_id"]].demand_weight
            for t in assigned_transfers
            if t["order_id"] in self.fleet_state.active_orders
        )
        broken_agent.state.current_load = max(0.0, broken_agent.state.current_load - transferred_weight)

        # Synchronize FleetState.vehicles atomically
        if failed_vehicle_id in self.fleet_state.vehicles:
            f_veh = self.fleet_state.vehicles[failed_vehicle_id]
            f_veh.assigned_orders = list(broken_agent.state.assigned_orders)
            f_veh.current_route = list(broken_agent.state.current_route)
            f_veh.current_load = broken_agent.state.current_load
            f_veh.status = VehicleStatus.BROKEN_DOWN

        for t in assigned_transfers:
            to_v_id = t["to_vehicle"]
            oid = t["order_id"]
            if to_v_id in self.fleet_state.vehicles:
                to_veh = self.fleet_state.vehicles[to_v_id]
                if oid not in to_veh.assigned_orders:
                    to_veh.assigned_orders.append(oid)
                to_veh.current_route = list(self.truck_agents[to_v_id].state.current_route)
                to_veh.current_load = self.truck_agents[to_v_id].state.current_load
            if oid in self.fleet_state.active_orders:
                ord_obj = self.fleet_state.active_orders[oid]
                ord_obj.assigned_vehicle_id = to_v_id
                ord_obj.status = OrderStatus.REASSIGNED

        self.mesh_network.set_node_failed(failed_vehicle_id, failed=True)

        return {
            "success": len(assigned_transfers) > 0,
            "transfers": assigned_transfers,
            "recovered_count": len(assigned_transfers),
            "recovered_orders_count": len(assigned_transfers),
            "unrecovered_count": len(broken_agent.state.assigned_orders),
            "mesh_messages": self.total_mesh_messages,
            "mesh_hops": self.total_mesh_hops,
        }

    def synchronize_state_on_reconnect(self) -> Dict[str, Any]:
        """
        Deterministic State Synchronization Policy upon cloud reconnection:
        1. Each TruckAgent reports its local active orders, cargo load, and executed stops.
        2. Conflict Resolution: If an order is claimed by multiple trucks, the truck with
           the smaller vehicle_id (or earliest confirmed timestamp) retains the order.
        3. Authoritative FleetState is updated and committed to central store.
        """
        conflicts_resolved = 0
        claimed_orders: Dict[str, str] = {}  # order_id -> vehicle_id

        for v_id, agent in self.truck_agents.items():
            for oid in agent.state.assigned_orders:
                if oid in claimed_orders:
                    # Conflict detected: apply deterministic tie-break
                    conflicts_resolved += 1
                    prior_veh = claimed_orders[oid]
                    # Retain lexicographically lower vehicle_id as canonical
                    if v_id < prior_veh:
                        claimed_orders[oid] = v_id
                        # Evict from prior agent
                        self.truck_agents[prior_veh].state.assigned_orders.remove(oid)
                    else:
                        agent.state.assigned_orders.remove(oid)
                else:
                    claimed_orders[oid] = v_id

        # Update FleetState with synchronized routes and assignments
        for v_id, agent in self.truck_agents.items():
            if v_id in self.fleet_state.vehicles:
                v = self.fleet_state.vehicles[v_id]
                v.current_route = list(agent.state.current_route)
                v.assigned_orders = list(agent.state.assigned_orders)
                v.current_load = agent.state.current_load
                v.status = agent.state.status

        self.fleet_state.connectivity_state = ConnectivityState.CLOUD_MODE
        return {
            "status": "SYNCHRONIZED",
            "conflicts_resolved": conflicts_resolved,
            "authoritative_assignments": claimed_orders,
        }

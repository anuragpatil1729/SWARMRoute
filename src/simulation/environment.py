from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, TrafficLevel, RoadStatus
from src.models.fleet_state import FleetState, ConnectivityState
from src.prediction.fuel import FuelModel, DeterministicFuelModel
from src.simulation.traffic import TrafficSimulator
from src.simulation.events import EventEngine, FleetEvent, EventType
from src.networking.mesh import MeshNetwork
from src.networking.connectivity import ConnectivityManager
from src.networking.messages import MeshMessage, MessageType
from src.optimization.dynamic_reoptimizer import DynamicReoptimizer
from src.evaluation.metrics import (
    calculate_total_cost,
    calculate_total_emissions,
    calculate_completion_rate,
    calculate_vehicle_utilization,
)


class SimulationSnapshot(BaseModel):
    """Timestamped snapshot of ongoing fleet simulation."""
    current_time_mins: float
    connectivity_mode: ConnectivityState
    active_vehicles_count: int
    broken_vehicles_count: int
    delivered_orders_count: int
    late_orders_count: int
    failed_orders_count: int
    total_fuel_liters: float
    total_co2_kg: float


class FleetSimulationEnvironment:
    """
    Closed-Loop Discrete-Time Simulation Environment for Autonomous Logistics Fleets.
    Implements a Gym-compatible step/observe/reset cycle:
      - Step-by-step edge progress (no customer teleportation).
      - Order lifecycles (PENDING -> LOADED -> IN_TRANSIT -> ARRIVED -> DELIVERED / LATE / FAILED).
      - Realistic time-window validation and service duration countdowns.
      - Fuel and emission physics evaluated dynamically on each movement step.
      - Mesh topology updates and event dispatch.
    """

    def __init__(
        self,
        fleet_state: FleetState,
        road_network: RoadNetwork,
        node_id_map: Dict[str, int],
        fuel_model: Optional[FuelModel] = None,
        traffic_sim: Optional[TrafficSimulator] = None,
        mesh_network: Optional[MeshNetwork] = None,
        step_size_mins: float = 1.0,
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
        self.step_size_mins = step_size_mins
        self.seed = seed

        self.delivered_orders: Set[str] = set()
        self.late_orders: Set[str] = set()
        self.failed_orders: Set[str] = set()
        self.total_distance_traveled_km = 0.0
        self.total_empty_distance_km = 0.0
        self.total_reassigned_orders_count = 0
        self.total_breakdowns_count = 0
        self.recovery_time_sec = 0.0
        self.total_fuel_liters = 0.0
        self.total_co2_kg = 0.0
        self.step_count = 0

        self._initialize_vehicle_states()

    def _initialize_vehicle_states(self) -> None:
        """Sets initial edge-tracking positions and initial cargo loading for all vehicles."""
        node_coords = self.road_network.node_coordinates
        for v_id, v in self.fleet_state.vehicles.items():
            if len(v.current_route) > 1:
                v.route_index = 0
                v.current_node = int(v.current_route[0])
                v.next_node = int(v.current_route[1])
                v.edge_progress_km = 0.0
                v.service_remaining_mins = 0.0
                curr_coord = node_coords.get(v.current_node, (0.0, 0.0))
                next_coord = node_coords.get(v.next_node, (0.0, 0.0))
                v.edge_total_km = math.hypot(next_coord[0] - curr_coord[0], next_coord[1] - curr_coord[1])
                v.current_location = curr_coord
                v.status = VehicleStatus.EN_ROUTE

                # Calculate initial load for orders on this route
                total_weight = 0.0
                for node in v.current_route[1:-1]:
                    node_int = int(node)
                    if node_int in self.reverse_node_map:
                        oid = self.reverse_node_map[node_int]
                        if oid in self.fleet_state.active_orders:
                            ord_obj = self.fleet_state.active_orders[oid]
                            ord_obj.status = OrderStatus.LOADED
                            ord_obj.assigned_vehicle_id = v_id
                            total_weight += ord_obj.demand_weight
                v.current_load = total_weight
            else:
                v.status = VehicleStatus.IDLE
                v.current_node = 0
                v.next_node = None
                v.current_location = node_coords.get(0, (0.0, 0.0))

            self.mesh_network.update_node_position(v_id, v.current_location)

    def reset(self, seed: Optional[int] = None) -> Dict[str, Any]:
        """Resets simulation clock, statistics, and returns initial observation."""
        if seed is not None:
            self.seed = seed
            self.traffic_sim = TrafficSimulator(seed=seed)
            self.mesh_network = MeshNetwork(seed=seed)

        self.current_time_mins = 0.0
        self.step_count = 0
        self.delivered_orders.clear()
        self.late_orders.clear()
        self.failed_orders.clear()
        self.total_distance_traveled_km = 0.0
        self.total_empty_distance_km = 0.0
        self.total_reassigned_orders_count = 0
        self.total_breakdowns_count = 0
        self.recovery_time_sec = 0.0
        self.total_fuel_liters = 0.0
        self.total_co2_kg = 0.0

        self._initialize_vehicle_states()
        return self.observe()

    def observe(self) -> Dict[str, Any]:
        """Returns the current state observation snapshot."""
        active_veh = sum(1 for v in self.fleet_state.vehicles.values() if v.status != VehicleStatus.BROKEN_DOWN and v.status != VehicleStatus.IDLE)
        broken_veh = sum(1 for v in self.fleet_state.vehicles.values() if v.status == VehicleStatus.BROKEN_DOWN)

        return {
            "current_time_mins": self.current_time_mins,
            "step_count": self.step_count,
            "connectivity_mode": self.fleet_state.connectivity_state.value,
            "active_vehicles": active_veh,
            "broken_vehicles": broken_veh,
            "delivered_orders": len(self.delivered_orders),
            "late_orders": len(self.late_orders),
            "failed_orders": len(self.failed_orders),
            "total_distance_km": round(self.total_distance_traveled_km, 2),
            "total_fuel_liters": round(self.total_fuel_liters, 2),
            "total_co2_kg": round(self.total_co2_kg, 2),
            "is_done": self.is_done(),
        }

    def execute_action(self, action: Dict[str, Any]) -> None:
        """
        Executes an agent decision action, such as a route modification,
        order reassignment, or delivery exchange.
        """
        action_type = action.get("type")
        node_coords = self.road_network.node_coordinates

        if action_type == "REASSIGN_ORDERS":
            transfers = action.get("transfers", [])
            self.total_reassigned_orders_count += len(transfers)
            for t in transfers:
                oid = t.get("order_id")
                from_v = t.get("from_vehicle")
                to_v = t.get("to_vehicle")

                # Remove from previous vehicle so it is no longer stranded
                if from_v in self.fleet_state.vehicles:
                    if oid in self.fleet_state.vehicles[from_v].assigned_orders:
                        self.fleet_state.vehicles[from_v].assigned_orders.remove(oid)
                    self.failed_orders.discard(oid)

                if to_v in self.fleet_state.vehicles and oid in self.fleet_state.active_orders:
                    v = self.fleet_state.vehicles[to_v]
                    ord_obj = self.fleet_state.active_orders[oid]
                    ord_node = self.node_id_map.get(oid)

                    if ord_node is not None:
                        # Insert before final depot stop
                        if len(v.current_route) > 1:
                            v.current_route.insert(-1, ord_node)
                        else:
                            v.current_route.append(ord_node)

                        if oid not in v.assigned_orders:
                            v.assigned_orders.append(oid)
                        v.current_load += ord_obj.demand_weight
                        ord_obj.assigned_vehicle_id = to_v
                        ord_obj.status = OrderStatus.REASSIGNED

        elif action_type == "UPDATE_ROUTE":
            v_id = action.get("vehicle_id")
            new_route = action.get("route", [])
            if v_id in self.fleet_state.vehicles and len(new_route) > 1:
                v = self.fleet_state.vehicles[v_id]
                v.current_route = new_route
                v.route_index = 0
                v.current_node = int(new_route[0])
                v.next_node = int(new_route[1])
                v.edge_progress_km = 0.0

    def step(self, action: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """
        Advances the simulation by step_size_mins.
        Returns (observation, reward, done, info) matching Gym interfaces.
        """
        self.step_count += 1
        if action:
            self.execute_action(action)

        self.current_time_mins += self.step_size_mins
        node_coords = self.road_network.node_coordinates

        # 1. Update traffic dynamics
        self.traffic_sim.update_road_network(self.road_network, self.current_time_mins)

        # 2. Pop and apply due scheduled events
        due_events = self.event_engine.pop_due_events(self.current_time_mins)
        for ev in due_events:
            self.event_engine.apply_event(ev, self.fleet_state)
            if ev.event_type == EventType.CONNECTIVITY_LOSS:
                self.conn_manager.on_cloud_lost()
            elif ev.event_type == EventType.CONNECTIVITY_RESTORED:
                self.conn_manager.on_cloud_restored()
            elif ev.event_type == EventType.VEHICLE_BREAKDOWN:
                self.total_breakdowns_count += 1
                v_id = ev.payload.get("vehicle_id")
                if v_id in self.fleet_state.vehicles:
                    self.fleet_state.vehicles[v_id].status = VehicleStatus.BROKEN_DOWN
                    self.mesh_network.set_node_failed(v_id, failed=True)

        # 3. Physically move active vehicles along edges
        for v_id, v in self.fleet_state.vehicles.items():
            if v.status == VehicleStatus.BROKEN_DOWN:
                continue

            # Case A: Vehicle currently servicing customer (unloading cargo)
            if v.service_remaining_mins > 0.0:
                v.service_remaining_mins -= self.step_size_mins
                if v.service_remaining_mins <= 0.0:
                    v.service_remaining_mins = 0.0
                    # Advance to next stop in route
                    v.route_index += 1
                    if v.route_index < len(v.current_route) - 1:
                        v.current_node = int(v.current_route[v.route_index])
                        v.next_node = int(v.current_route[v.route_index + 1])
                        v.edge_progress_km = 0.0
                        curr_coord = node_coords.get(v.current_node, (0.0, 0.0))
                        next_coord = node_coords.get(v.next_node, (0.0, 0.0))
                        v.edge_total_km = math.hypot(next_coord[0] - curr_coord[0], next_coord[1] - curr_coord[1])
                        v.status = VehicleStatus.EN_ROUTE
                    else:
                        # Reached end of tour (Depot)
                        v.status = VehicleStatus.IDLE
                        v.next_node = None
                continue

            # Case B: Vehicle moving along active edge
            if v.status == VehicleStatus.EN_ROUTE and v.next_node is not None:
                # Check current traffic speed on edge
                u, nxt = v.current_node, v.next_node
                traffic_mult = 1.0
                if self.road_network.graph.has_edge(u, nxt):
                    road_obj = self.road_network.graph[u][nxt].get("road")
                    if road_obj:
                        traffic_mult = road_obj.traffic_level.speed_multiplier
                        if road_obj.status == RoadStatus.CLOSED:
                            traffic_mult = 0.001

                effective_speed = max(1.0, v.average_speed * traffic_mult)
                v.current_speed_kmh = effective_speed

                # Distance moved in this discrete time step
                dist_moved = effective_speed * (self.step_size_mins / 60.0)
                # Cap to remaining edge distance
                remaining_on_edge = max(0.0, v.edge_total_km - v.edge_progress_km)
                actual_move = min(dist_moved, remaining_on_edge)
                v.edge_progress_km += actual_move
                self.total_distance_traveled_km += actual_move
                if v.current_load <= 1e-6:
                    self.total_empty_distance_km += actual_move

                # Compute step fuel consumption
                # Physics model: base rate + payload factor + traffic multiplier
                step_fuel = (v.fuel_efficiency / 100.0) * actual_move * (1.0 + 0.3 * (v.current_load / max(v.max_weight, 1.0))) * (1.0 / max(traffic_mult, 0.1))
                v.fuel_level = max(0.0, v.fuel_level - step_fuel)
                self.total_fuel_liters += step_fuel
                self.total_co2_kg += step_fuel * 2.68

                # Update spatial coordinate
                curr_coord = node_coords.get(v.current_node, (0.0, 0.0))
                next_coord = node_coords.get(v.next_node, (0.0, 0.0))
                progress_ratio = min(1.0, v.edge_progress_km / max(v.edge_total_km, 1e-4))
                v.current_location = (
                    curr_coord[0] + progress_ratio * (next_coord[0] - curr_coord[0]),
                    curr_coord[1] + progress_ratio * (next_coord[1] - curr_coord[1]),
                )
                self.mesh_network.update_node_position(v_id, v.current_location)

                # Check arrival at destination node
                if v.edge_progress_km >= v.edge_total_km - 1e-4:
                    arrived_node = v.next_node
                    v.current_node = arrived_node
                    v.current_location = next_coord
                    v.edge_progress_km = 0.0

                    # Check if arrived node is a customer order delivery
                    if arrived_node in self.reverse_node_map:
                        oid = self.reverse_node_map[arrived_node]
                        if oid in self.fleet_state.active_orders:
                            ord_obj = self.fleet_state.active_orders[oid]
                            ord_obj.actual_arrival_time = self.current_time_mins

                            if self.current_time_mins > ord_obj.latest_delivery:
                                ord_obj.status = OrderStatus.LATE
                                self.late_orders.add(oid)
                            else:
                                ord_obj.status = OrderStatus.DELIVERED

                            self.delivered_orders.add(oid)
                            ord_obj.actual_delivery_time = self.current_time_mins + ord_obj.service_time

                            # Unload cargo
                            v.current_load = max(0.0, v.current_load - ord_obj.demand_weight)
                            v.current_volume_load = max(0.0, v.current_volume_load - ord_obj.volume)

                            # Start service time
                            v.service_remaining_mins = max(0.0, ord_obj.service_time)
                            v.status = VehicleStatus.DELIVERING
                    else:
                        # Reached non-order node (e.g. waypoint or depot)
                        v.route_index += 1
                        if v.route_index < len(v.current_route) - 1:
                            v.current_node = int(v.current_route[v.route_index])
                            v.next_node = int(v.current_route[v.route_index + 1])
                            curr_c = node_coords.get(v.current_node, (0.0, 0.0))
                            next_c = node_coords.get(v.next_node, (0.0, 0.0))
                            v.edge_total_km = math.hypot(next_c[0] - curr_c[0], next_c[1] - curr_c[1])
                            v.edge_progress_km = 0.0
                            v.status = VehicleStatus.EN_ROUTE
                        else:
                            v.status = VehicleStatus.IDLE
                            v.next_node = None

        # 4. Check for unserved orders on broken vehicles or unassigned orders during cloud outage
        for v_id, v in self.fleet_state.vehicles.items():
            if v.status == VehicleStatus.BROKEN_DOWN:
                for oid in v.assigned_orders:
                    if oid not in self.delivered_orders:
                        self.failed_orders.add(oid)
                        if oid in self.fleet_state.active_orders:
                            self.fleet_state.active_orders[oid].status = OrderStatus.FAILED

        if self.fleet_state.connectivity_state != ConnectivityState.CLOUD_MODE:
            all_assigned = {oid for veh in self.fleet_state.vehicles.values() for oid in veh.assigned_orders}
            for oid, ord_obj in self.fleet_state.active_orders.items():
                if oid not in all_assigned and oid not in self.delivered_orders:
                    self.failed_orders.add(oid)
                    ord_obj.status = OrderStatus.FAILED

        # 5. Calculate reward (negative cost step)
        step_reward = -1.0 * (
            1.0 * (self.total_distance_traveled_km)
            + 2.0 * self.total_fuel_liters
            + 10.0 * (len(self.late_orders) * 0.5)
        )
        done = self.is_done()
        obs = self.observe()
        info = {
            "due_events_count": len(due_events),
            "delivered_orders": list(self.delivered_orders),
            "late_orders": list(self.late_orders),
            "failed_orders": list(self.failed_orders),
        }

        return obs, step_reward, done, info

    def is_done(self) -> bool:
        """Returns True if all reachable orders are delivered or all vehicles are idle/broken."""
        total_orders = len(self.fleet_state.active_orders)
        if total_orders > 0 and len(self.delivered_orders) + len(self.failed_orders) >= total_orders:
            return True

        # All vehicles finished route or broken down
        all_stopped = all(
            v.status in (VehicleStatus.IDLE, VehicleStatus.BROKEN_DOWN)
            for v in self.fleet_state.vehicles.values()
        )
        return all_stopped

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates exact, un-fabricated metrics from actual simulation history."""
        total_orders = len(self.fleet_state.active_orders)
        delivered_count = len(self.delivered_orders)
        late_count = len(self.late_orders)
        failed_count = len(self.failed_orders)
        completion_rate = calculate_completion_rate(total_orders, delivered_count)

        # Max lateness and average delivery delay
        max_lateness = 0.0
        total_delay = 0.0
        for oid in self.late_orders:
            if oid in self.fleet_state.active_orders:
                o = self.fleet_state.active_orders[oid]
                arr = o.actual_arrival_time or self.current_time_mins
                delay = max(0.0, arr - o.latest_delivery)
                max_lateness = max(max_lateness, delay)
                total_delay += delay

        avg_delay = round(total_delay / max(1, delivered_count), 2)
        mesh_stats = self.mesh_network.get_mesh_metrics()
        utilization = calculate_vehicle_utilization(list(self.fleet_state.vehicles.values()))

        cost = calculate_total_cost(
            distance_km=self.total_distance_traveled_km,
            fuel_liters=self.total_fuel_liters,
            delay_hours=(max_lateness * late_count) / 60.0,
            emissions_kg=self.total_co2_kg,
            vehicles_used=sum(1 for v in self.fleet_state.vehicles.values() if v.status != VehicleStatus.BROKEN_DOWN),
        )

        return {
            "total_distance_km": round(self.total_distance_traveled_km, 2),
            "total_fuel_liters": round(self.total_fuel_liters, 2),
            "total_co2_kg": round(self.total_co2_kg, 2),
            "total_orders": total_orders,
            "completed_deliveries": delivered_count,
            "failed_orders": failed_count,
            "late_deliveries": late_count,
            "completion_rate_pct": completion_rate,
            "average_delivery_delay_mins": avg_delay,
            "max_lateness_mins": round(max_lateness, 2),
            "vehicle_utilization_pct": utilization,
            "empty_distance_km": round(self.total_empty_distance_km, 2),
            "recovery_time_sec": round(self.recovery_time_sec, 4),
            "reassigned_deliveries_count": self.total_reassigned_orders_count,
            "breakdown_count": self.total_breakdowns_count,
            "mesh_messages_sent": mesh_stats["total_messages"],
            "mesh_delivery_success": mesh_stats["delivery_success"],
            "average_mesh_latency_ms": mesh_stats["average_latency_ms"],
            "average_mesh_hops": mesh_stats["average_hops"],
            "total_cost": cost,
            "simulation_duration_mins": self.current_time_mins,
        }

from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, Field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.models.order import Order
from src.models.vehicle import Vehicle
from src.models.road import RoadNetwork, TrafficLevel
from src.prediction.fuel import FuelModel, DeterministicFuelModel


class OptimizationResult(BaseModel):
    """
    Standard result returned by routing and fleet optimization engines.
    """
    status: str = Field(..., description="Solver status: OPTIMAL, FEASIBLE, INFEASIBLE, NOT_SOLVED")
    routes: Dict[str, List[int]] = Field(default_factory=dict, description="Vehicle ID to stop sequence")
    order_assignments: Dict[str, List[str]] = Field(default_factory=dict, description="Vehicle ID to assigned order IDs")
    arrival_times: Dict[str, Dict[int, float]] = Field(default_factory=dict, description="Arrival time at each stop")
    departure_times: Dict[str, Dict[int, float]] = Field(default_factory=dict, description="Departure time at each stop")
    lateness_per_order: Dict[str, float] = Field(default_factory=dict, description="Lateness beyond due date per order")
    total_distance: float = Field(default=0.0, description="Total distance traveled (km)")
    total_travel_time: float = Field(default=0.0, description="Total travel time across all active vehicles")
    total_fuel: float = Field(default=0.0, description="Total fuel consumed (Liters)")
    total_emissions: float = Field(default=0.0, description="Total CO2 emissions (kg)")
    late_deliveries_count: int = Field(default=0, description="Number of orders delivered late")
    max_lateness: float = Field(default=0.0, description="Maximum lateness encountered (time units)")
    active_vehicles_count: int = Field(default=0, description="Number of vehicles with non-empty routes")
    fleet_utilization: float = Field(default=0.0, description="Average capacity utilization (%)")
    cost_breakdown: Dict[str, float] = Field(default_factory=dict, description="Cost components from objective weights")
    total_objective_cost: float = Field(default=0.0, description="Weighted multi-objective cost total")
    computation_time_sec: float = Field(default=0.0, description="Time spent solving in seconds")
    unassigned_orders: List[str] = Field(default_factory=list, description="Orders dropped/unassigned if any")


class VRPTWSolver:
    """
    Industry-grade Google OR-Tools CVRPTW Solver.
    Enforces vehicle capacity, time windows, service times, and multi-vehicle coordination.
    Calculates multi-objective post-optimization metrics based on distance, fuel, emissions,
    delay penalties, vehicle usage, and risk.
    """

    DEFAULT_OBJECTIVE_WEIGHTS = {
        "distance": 1.0,
        "fuel": 2.0,
        "delay": 10.0,
        "emissions": 3.0,
        "vehicle_usage": 5.0,
        "risk": 4.0,
    }

    def __init__(
        self,
        fuel_model: Optional[FuelModel] = None,
        objective_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.fuel_model = fuel_model or DeterministicFuelModel()
        self.objective_weights = objective_weights or self.DEFAULT_OBJECTIVE_WEIGHTS.copy()

    def solve(
        self,
        vehicles: List[Vehicle],
        orders: List[Order],
        road_network: RoadNetwork,
        time_limit_sec: int = 30,
        allow_drop: bool = False,
        drop_penalty: int = 100000,
        travel_time_predictor: Optional[Any] = None,
        fuel_predictor: Optional[Any] = None,
    ) -> OptimizationResult:
        """
        Solves the CVRPTW problem instance using OR-Tools.
        """
        start_wall_time = time.time()

        if not orders:
            return OptimizationResult(
                status="FEASIBLE",
                computation_time_sec=time.time() - start_wall_time,
            )

        num_vehicles = len(vehicles)
        if num_vehicles == 0:
            return OptimizationResult(
                status="INFEASIBLE",
                unassigned_orders=[o.order_id for o in orders],
                computation_time_sec=time.time() - start_wall_time,
            )

        # Mapping: Index 0 is Depot. Indices 1..N correspond to orders[0..N-1].
        num_nodes = len(orders) + 1
        node_ids = [0] + [i + 1 for i in range(len(orders))]
        order_map: Dict[int, Order] = {i + 1: order for i, order in enumerate(orders)}

        # 1. Compute Distance and Time matrices (scaled to integer precision for OR-Tools)
        # OR-Tools routing solver requires integer costs/times
        SCALE = 100  # 2 decimal places precision

        dist_matrix_raw, time_matrix_raw = road_network.build_complete_euclidean_matrix(node_ids)

        if travel_time_predictor is not None and getattr(travel_time_predictor, "is_trained", False):
            pairs = []
            pair_indices = []
            for i in range(num_nodes):
                for j in range(num_nodes):
                    if i != j:
                        pairs.append([dist_matrix_raw[i][j], 10.0, 2, 45.0, 1, 1, 0, 100.0])
                        pair_indices.append((i, j))
            if pairs:
                pred_hrs_batch = travel_time_predictor.predict(np.array(pairs))
                for (i, j), pred_hrs in zip(pair_indices, pred_hrs_batch):
                    time_matrix_raw[i][j] = float(pred_hrs) * 60.0

        if fuel_predictor is not None and getattr(fuel_predictor, "is_trained", False):
            fuel_wt = self.objective_weights.get("fuel", 1.5)
            pairs = []
            pair_indices = []
            for i in range(num_nodes):
                for j in range(num_nodes):
                    if i != j:
                        pairs.append([dist_matrix_raw[i][j], 0, 100.0, 40.0, 1, 0.0, 1])
                        pair_indices.append((i, j))
            if pairs:
                pred_fuel_batch = fuel_predictor.predict(np.array(pairs))
                for (i, j), pred_fuel in zip(pair_indices, pred_fuel_batch):
                    dist_matrix_raw[i][j] = dist_matrix_raw[i][j] + (fuel_wt * float(pred_fuel))

        int_dist_matrix = [
            [int(round(dist_matrix_raw[i][j] * SCALE)) for j in range(num_nodes)]
            for i in range(num_nodes)
        ]
        int_time_matrix = [
            [int(round(time_matrix_raw[i][j] * SCALE)) for j in range(num_nodes)]
            for i in range(num_nodes)
        ]

        # Service times (scaled)
        int_service_times = [0] * num_nodes
        for node_idx, ord_obj in order_map.items():
            int_service_times[node_idx] = int(round(ord_obj.service_time * SCALE))

        # Demands (integer scaled)
        int_demands = [0] * num_nodes
        for node_idx, ord_obj in order_map.items():
            int_demands[node_idx] = int(round(ord_obj.demand_weight))

        # Vehicle capacities
        int_vehicle_capacities = [int(round(v.max_weight)) for v in vehicles]

        # Time windows (scaled)
        depot_node = road_network.graph.nodes.get(0, {})
        depot_due = depot_node.get("due_date", 2400.0)
        time_windows = [(0, int(round(depot_due * SCALE)))]  # Depot

        for node_idx in range(1, num_nodes):
            ord_obj = order_map[node_idx]
            earliest = int(round(ord_obj.earliest_delivery * SCALE))
            latest = int(round(ord_obj.latest_delivery * SCALE))
            time_windows.append((earliest, latest))

        # 2. Create Routing Index Manager and Routing Model
        manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)

        # 3. Define Transit Distance Callback & Cost Evaluator
        def distance_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int_dist_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # 4. Add Capacity Dimension (CVRP)
        def demand_callback(from_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            return int_demands[from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            int_vehicle_capacities,
            True,  # start cumul to zero
            "Capacity",
        )

        # 5. Add Time Dimension with Time Windows (VRPTW)
        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # transit time + service time at departure node
            return int_time_matrix[from_node][to_node] + int_service_times[from_node]

        time_callback_index = routing.RegisterTransitCallback(time_callback)
        max_time_horizon = int(round(depot_due * SCALE * 2))

        routing.AddDimension(
            time_callback_index,
            max_time_horizon,  # allow waiting time / slack
            max_time_horizon,  # maximum time per vehicle route
            False,  # Don't force start cumul to zero (allows vehicles to depart later if optimal)
            "Time",
        )
        time_dimension = routing.GetDimensionOrDie("Time")

        # Set time windows for every customer stop
        for location_idx, (open_time, close_time) in enumerate(time_windows):
            index = manager.NodeToIndex(location_idx)
            if index != -1:
                time_dimension.CumulVar(index).SetRange(open_time, close_time)

        # Set depot time window bounds for each vehicle start & end
        for vehicle_id in range(num_vehicles):
            start_index = routing.Start(vehicle_id)
            end_index = routing.End(vehicle_id)
            time_dimension.CumulVar(start_index).SetRange(time_windows[0][0], time_windows[0][1])
            time_dimension.CumulVar(end_index).SetRange(time_windows[0][0], time_windows[0][1])

        # Optional disjunction: drop orders if unroutable
        if allow_drop:
            for node_idx in range(1, num_nodes):
                routing.AddDisjunction([manager.NodeToIndex(node_idx)], drop_penalty)

        # 6. Configure Search Parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = max(1, time_limit_sec)

        # 7. Solve
        solution = routing.SolveWithParameters(search_parameters)
        elapsed_sec = time.time() - start_wall_time

        if not solution:
            # Check if solver found it infeasible
            solver_status = "INFEASIBLE"
            return OptimizationResult(
                status=solver_status,
                unassigned_orders=[o.order_id for o in orders],
                computation_time_sec=elapsed_sec,
            )

        # 8. Extract Solution Details
        routes: Dict[str, List[int]] = {}
        order_assignments: Dict[str, List[str]] = {}
        arrival_times: Dict[str, Dict[int, float]] = {}
        departure_times: Dict[str, Dict[int, float]] = {}
        lateness_dict: Dict[str, float] = {}

        total_distance = 0.0
        total_travel_time = 0.0
        total_fuel = 0.0
        total_co2 = 0.0
        late_deliveries_count = 0
        max_lateness = 0.0
        active_vehicles = 0
        total_capacity_used = 0.0
        total_capacity_available = 0.0

        for v_idx, vehicle in enumerate(vehicles):
            v_id = vehicle.vehicle_id
            index = routing.Start(v_idx)
            route_nodes: List[int] = []
            assigned_orders_list: List[str] = []
            v_arrivals: Dict[int, float] = {}
            v_departures: Dict[int, float] = {}

            v_dist = 0.0
            v_time = 0.0
            v_stops = 0
            v_load = 0.0

            while not routing.IsEnd(index):
                node_idx = manager.IndexToNode(index)
                time_var = time_dimension.CumulVar(index)
                arr_time = solution.Min(time_var) / SCALE
                route_nodes.append(node_idx)
                v_arrivals[node_idx] = arr_time

                if node_idx != 0:
                    ord_obj = order_map[node_idx]
                    assigned_orders_list.append(ord_obj.order_id)
                    v_stops += 1
                    v_load += ord_obj.demand_weight

                    # Check lateness
                    lat = ord_obj.lateness(arr_time)
                    if lat > 1e-4:
                        late_deliveries_count += 1
                        max_lateness = max(max_lateness, lat)
                        lateness_dict[ord_obj.order_id] = lat

                    dep_time = arr_time + ord_obj.service_time
                    v_departures[node_idx] = dep_time
                else:
                    v_departures[node_idx] = arr_time

                next_index = solution.Value(routing.NextVar(index))
                next_node = manager.IndexToNode(next_index)
                step_dist = dist_matrix_raw[node_idx][next_node]
                step_time = time_matrix_raw[node_idx][next_node]
                v_dist += step_dist
                v_time += step_time

                index = next_index

            # End depot node
            end_node = manager.IndexToNode(index)
            end_time = solution.Min(time_dimension.CumulVar(index)) / SCALE
            route_nodes.append(end_node)
            v_arrivals[end_node] = end_time
            v_departures[end_node] = end_time

            routes[v_id] = route_nodes
            order_assignments[v_id] = assigned_orders_list
            arrival_times[v_id] = v_arrivals
            departure_times[v_id] = v_departures

            if v_stops > 0:
                active_vehicles += 1
                total_capacity_used += v_load
                total_capacity_available += vehicle.max_weight

                # Calculate Fuel and CO2 leg-by-leg along the route
                demands_dict = {node: order_map[node].demand_weight for node in route_nodes if node != 0}
                _, v_fuel, v_co2 = self.fuel_model.calculate_route_fuel(
                    route=route_nodes,
                    road_network=road_network,
                    vehicle_type=vehicle.vehicle_type,
                    max_weight=vehicle.max_weight,
                    average_speed=vehicle.average_speed,
                    customer_demands=demands_dict,
                )

                total_distance += v_dist
                total_travel_time += v_time
                total_fuel += v_fuel
                total_co2 += v_co2

        # 9. Compute Unassigned Orders
        assigned_set = set()
        for ord_list in order_assignments.values():
            assigned_set.update(ord_list)
        unassigned = [o.order_id for o in orders if o.order_id not in assigned_set]

        # 10. Multi-objective Cost Calculation
        w = self.objective_weights
        dist_cost = total_distance * w.get("distance", 1.0)
        fuel_cost = total_fuel * w.get("fuel", 2.0)
        emissions_cost = total_co2 * w.get("emissions", 3.0)
        delay_cost = sum(lateness_dict.values()) * w.get("delay", 10.0)
        usage_cost = active_vehicles * w.get("vehicle_usage", 5.0)
        risk_cost = 0.0  # Baseline normal conditions

        total_cost = dist_cost + fuel_cost + emissions_cost + delay_cost + usage_cost + risk_cost
        utilization = (
            (total_capacity_used / max(1.0, total_capacity_available)) * 100.0
            if total_capacity_available > 0
            else 0.0
        )

        return OptimizationResult(
            status="OPTIMAL" if routing.status() == 1 else "FEASIBLE",
            routes=routes,
            order_assignments=order_assignments,
            arrival_times=arrival_times,
            departure_times=departure_times,
            lateness_per_order=lateness_dict,
            total_distance=round(total_distance, 2),
            total_travel_time=round(total_travel_time, 2),
            total_fuel=round(total_fuel, 2),
            total_emissions=round(total_co2, 2),
            late_deliveries_count=late_deliveries_count,
            max_lateness=round(max_lateness, 2),
            active_vehicles_count=active_vehicles,
            fleet_utilization=round(utilization, 2),
            cost_breakdown={
                "distance_cost": round(dist_cost, 2),
                "fuel_cost": round(fuel_cost, 2),
                "emissions_cost": round(emissions_cost, 2),
                "delay_cost": round(delay_cost, 2),
                "vehicle_usage_cost": round(usage_cost, 2),
                "risk_cost": round(risk_cost, 2),
            },
            total_objective_cost=round(total_cost, 2),
            computation_time_sec=round(elapsed_sec, 3),
            unassigned_orders=unassigned,
        )

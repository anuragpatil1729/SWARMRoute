from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from src.models.order import Order
from src.models.vehicle import Vehicle
from src.models.road import RoadNetwork, TrafficLevel
from src.models.fleet_state import FleetState
from src.prediction.fuel import FuelModel, DeterministicFuelModel
from src.optimization.vrptw import VRPTWSolver, OptimizationResult
from src.evaluation.metrics import FleetMetrics


class NearestNeighborBaseline:
    """
    Standard Nearest-Neighbor Heuristic for CVRPTW.
    Serves as the conventional simple baseline that advanced optimizers must beat.
    """

    def __init__(self, fuel_model: Optional[FuelModel] = None) -> None:
        self.fuel_model = fuel_model or DeterministicFuelModel()

    def solve(
        self,
        vehicles: List[Vehicle],
        orders: List[Order],
        road_network: RoadNetwork,
        objective_weights: Optional[Dict[str, float]] = None,
    ) -> OptimizationResult:
        start_time = time.time()
        weights = objective_weights or VRPTWSolver.DEFAULT_OBJECTIVE_WEIGHTS

        unserved_orders = list(orders)
        routes: Dict[str, List[int]] = {v.vehicle_id: [0] for v in vehicles}
        order_assignments: Dict[str, List[str]] = {v.vehicle_id: [] for v in vehicles}
        arrival_times: Dict[str, Dict[int, float]] = {v.vehicle_id: {0: 0.0} for v in vehicles}
        departure_times: Dict[str, Dict[int, float]] = {v.vehicle_id: {0: 0.0} for v in vehicles}
        lateness_dict: Dict[str, float] = {}

        # Node coordinates map
        node_id_to_order = {i + 1: o for i, o in enumerate(orders)}
        order_id_to_node = {o.order_id: i + 1 for i, o in enumerate(orders)}

        total_distance = 0.0
        total_time = 0.0
        total_fuel = 0.0
        total_co2 = 0.0
        late_count = 0
        max_late = 0.0
        active_veh = 0
        total_used_weight = 0.0
        total_avail_weight = 0.0

        for v in vehicles:
            curr_node = 0
            curr_time = 0.0
            curr_load = 0.0
            v_dist = 0.0
            v_time = 0.0
            v_stops = 0

            while unserved_orders:
                # Find nearest feasible unserved order
                best_order: Optional[Order] = None
                best_node = None
                best_dist = float("inf")

                for ord_cand in unserved_orders:
                    n_idx = order_id_to_node[ord_cand.order_id]
                    dist = road_network.get_distance(curr_node, n_idx)
                    # Check capacity
                    if curr_load + ord_cand.demand_weight <= v.max_weight:
                        if dist < best_dist:
                            best_dist = dist
                            best_order = ord_cand
                            best_node = n_idx

                if best_order is None:
                    # Vehicle full or no order reachable
                    break

                # Advance to best order
                unserved_orders.remove(best_order)
                transit_time = road_network.get_travel_time(curr_node, best_node, v.average_speed)
                curr_dist = best_dist
                arr_time = max(curr_time + transit_time, best_order.earliest_delivery)
                lat = best_order.lateness(arr_time)
                if lat > 1e-4:
                    late_count += 1
                    max_late = max(max_late, lat)
                    lateness_dict[best_order.order_id] = lat

                dep_time = arr_time + best_order.service_time

                routes[v.vehicle_id].append(best_node)
                order_assignments[v.vehicle_id].append(best_order.order_id)
                arrival_times[v.vehicle_id][best_node] = round(arr_time, 2)
                departure_times[v.vehicle_id][best_node] = round(dep_time, 2)

                curr_node = best_node
                curr_time = dep_time
                curr_load += best_order.demand_weight
                v_dist += curr_dist
                v_time += transit_time
                v_stops += 1

            # Return to depot
            if v_stops > 0:
                ret_dist = road_network.get_distance(curr_node, 0)
                ret_time = road_network.get_travel_time(curr_node, 0, v.average_speed)
                arr_depot = curr_time + ret_time
                routes[v.vehicle_id].append(0)
                arrival_times[v.vehicle_id][0] = round(arr_depot, 2)
                departure_times[v.vehicle_id][0] = round(arr_depot, 2)
                v_dist += ret_dist
                v_time += ret_time

                v_fuel = self.fuel_model.calculate_fuel(
                    vehicle_type=v.vehicle_type,
                    vehicle_load=curr_load,
                    max_weight=v.max_weight,
                    distance=v_dist,
                    average_speed=v.average_speed,
                    traffic_level=TrafficLevel.NORMAL,
                    road_gradient=0.0,
                    stop_count=v_stops,
                )
                v_co2 = self.fuel_model.calculate_co2(v_fuel)

                total_distance += v_dist
                total_time += v_time
                total_fuel += v_fuel
                total_co2 += v_co2
                active_veh += 1
                total_used_weight += curr_load
                total_avail_weight += v.max_weight

        elapsed = time.time() - start_time
        dist_cost = total_distance * weights.get("distance", 1.0)
        fuel_cost = total_fuel * weights.get("fuel", 2.0)
        delay_cost = sum(lateness_dict.values()) * weights.get("delay", 10.0)
        emiss_cost = total_co2 * weights.get("emissions", 3.0)
        usage_cost = active_veh * weights.get("vehicle_usage", 5.0)
        risk_cost = 0.0
        total_cost = dist_cost + fuel_cost + delay_cost + emiss_cost + usage_cost + risk_cost

        utilization = (
            (total_used_weight / max(1.0, total_avail_weight)) * 100.0 if total_avail_weight > 0 else 0.0
        )

        return OptimizationResult(
            status="FEASIBLE",
            routes=routes,
            order_assignments=order_assignments,
            arrival_times=arrival_times,
            departure_times=departure_times,
            lateness_per_order=lateness_dict,
            total_distance=round(total_distance, 2),
            total_travel_time=round(total_time, 2),
            total_fuel=round(total_fuel, 2),
            total_emissions=round(total_co2, 2),
            late_deliveries_count=late_count,
            max_lateness=round(max_late, 2),
            active_vehicles_count=active_veh,
            fleet_utilization=round(utilization, 2),
            cost_breakdown={
                "distance_cost": round(dist_cost, 2),
                "fuel_cost": round(fuel_cost, 2),
                "emissions_cost": round(emiss_cost, 2),
                "delay_cost": round(delay_cost, 2),
                "vehicle_usage_cost": round(usage_cost, 2),
                "risk_cost": round(risk_cost, 2),
            },
            total_objective_cost=round(total_cost, 2),
            computation_time_sec=round(elapsed, 3),
            unassigned_orders=[o.order_id for o in unserved_orders],
        )


def run_benchmark_comparison(
    fleet_state: FleetState,
    road_network: RoadNetwork,
    dataset_name: str = "Solomon C101",
    time_limit_sec: int = 15,
) -> Tuple[FleetMetrics, FleetMetrics, Dict[str, float]]:
    """
    Compares Baseline Heuristic (Nearest-Neighbor) against OR-Tools CVRPTW Optimizer.
    Computes comparative percentage improvements.
    """
    vehicles = list(fleet_state.vehicles.values())
    orders = list(fleet_state.active_orders.values())

    # 1. Run Nearest Neighbor Heuristic
    nn_baseline = NearestNeighborBaseline()
    nn_result = nn_baseline.solve(vehicles, orders, road_network)

    baseline_metrics = FleetMetrics(
        system_name="BASELINE (Nearest-Neighbor)",
        dataset_name=dataset_name,
        num_vehicles_used=nn_result.active_vehicles_count,
        total_vehicles_available=len(vehicles),
        total_orders=len(orders),
        delivered_orders=len(orders) - len(nn_result.unassigned_orders),
        total_distance_km=nn_result.total_distance,
        total_travel_time_hrs=nn_result.total_travel_time,
        total_fuel_liters=nn_result.total_fuel,
        total_co2_kg=nn_result.total_emissions,
        late_deliveries=nn_result.late_deliveries_count,
        max_lateness=nn_result.max_lateness,
        vehicle_utilization_pct=nn_result.fleet_utilization,
        total_cost=nn_result.total_objective_cost,
        runtime_seconds=nn_result.computation_time_sec,
    )

    # 2. Run OR-Tools VRPTW Solver
    ortools_solver = VRPTWSolver()
    opt_result = ortools_solver.solve(vehicles, orders, road_network, time_limit_sec=time_limit_sec)

    opt_metrics = FleetMetrics(
        system_name="AI/OPTIMIZATION SYSTEM (OR-Tools CVRPTW)",
        dataset_name=dataset_name,
        num_vehicles_used=opt_result.active_vehicles_count,
        total_vehicles_available=len(vehicles),
        total_orders=len(orders),
        delivered_orders=len(orders) - len(opt_result.unassigned_orders),
        total_distance_km=opt_result.total_distance,
        total_travel_time_hrs=opt_result.total_travel_time,
        total_fuel_liters=opt_result.total_fuel,
        total_co2_kg=opt_result.total_emissions,
        late_deliveries=opt_result.late_deliveries_count,
        max_lateness=opt_result.max_lateness,
        vehicle_utilization_pct=opt_result.fleet_utilization,
        total_cost=opt_result.total_objective_cost,
        runtime_seconds=opt_result.computation_time_sec,
    )

    # 3. Compute Improvements (%)
    def calc_reduction(base_val: float, opt_val: float) -> float:
        if base_val <= 0:
            return 0.0
        return ((base_val - opt_val) / base_val) * 100.0

    improvements = {
        "fuel_reduction_pct": round(
            calc_reduction(baseline_metrics.total_fuel_liters, opt_metrics.total_fuel_liters), 2
        ),
        "co2_reduction_pct": round(
            calc_reduction(baseline_metrics.total_co2_kg, opt_metrics.total_co2_kg), 2
        ),
        "distance_reduction_pct": round(
            calc_reduction(baseline_metrics.total_distance_km, opt_metrics.total_distance_km), 2
        ),
        "cost_reduction_pct": round(
            calc_reduction(baseline_metrics.total_cost, opt_metrics.total_cost), 2
        ),
        "late_deliveries_reduction_pct": round(
            calc_reduction(baseline_metrics.late_deliveries, opt_metrics.late_deliveries), 2
        ),
    }

    return baseline_metrics, opt_metrics, improvements

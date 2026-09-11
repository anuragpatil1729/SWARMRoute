#!/usr/bin/env python3
"""
SWARMRoute: Interactive End-to-End Simulation Demo
Executes the full closed-loop lifecycle:
1. Fleet initialization
2. Customer/order generation (Solomon C101)
3. Initial route optimization (OR-Tools CVRPTW)
4. Vehicle movement and dynamic simulation ticks
5. Traffic congestion dynamics
6. Vehicle mechanical breakdown
7. Cloud disconnection/outage (Transition to Mesh Mode)
8. Peer-to-peer RF mesh communication
9. Stranded order detection
10. Decentralized contract-net bidding
11. Atomic order reassignment
12. Continued route execution and delivery completion
13. Authoritative final simulation metrics
"""
from __future__ import annotations
import argparse
import copy
import math
import sys
import time
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safeguard against PyTorch/Keras ARM64 collision
for _m in ("pyarrow", "tensorflow", "keras", "tensorboard"):
    if _m not in sys.modules:
        sys.modules[_m] = None

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.order import Order, OrderStatus
from src.models.road import RoadNetwork, TrafficLevel
from src.data.loaders.solomon import load_solomon_benchmark
from src.optimization.route_optimizer import RouteOptimizer
from src.prediction.fuel import DeterministicFuelModel
from src.simulation.environment import FleetSimulationEnvironment
from src.simulation.events import FleetEvent, EventType
from src.networking.mesh import MeshNetwork
from src.agents.fleet_agent import FleetAgent
from src.evaluation.metrics import calculate_communication_overhead


def format_time(mins: float) -> str:
    """Formats simulation minutes as [HH:MM]."""
    hrs = int(mins // 60)
    rem_mins = int(mins % 60)
    return f"[{hrs:02d}:{rem_mins:02d}]"


def run_demo(
    dataset: str = "C101",
    customers: int = 25,
    vehicles: int = 5,
    breakdown_time: float = 80.0,
    duration_mins: float = 1200.0,
    seed: int = 42,
) -> dict:
    print("=== SWARMRoute Simulation ===")
    
    # 1. Fleet & Order Initialization
    fleet_state, road_network, meta = load_solomon_benchmark(
        dataset, max_customers=customers, vehicle_count=vehicles
    )
    orders = list(fleet_state.active_orders.values())
    node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}
    fuel_model = DeterministicFuelModel()
    mesh = MeshNetwork(transmission_range_km=30.0, seed=seed)

    print(f"Fleet initialized: {len(fleet_state.vehicles)} vehicles")
    print(f"Customers: {len(orders)}")

    # 2. Initial Route Optimization
    t0_opt = time.perf_counter()
    optimizer = RouteOptimizer(fuel_model=fuel_model)
    sol = optimizer.optimize(fleet=fleet_state, orders=orders, road_network=road_network, time_limit_sec=4)
    opt_time = time.perf_counter() - t0_opt

    for vid, route in sol.routes.items():
        if vid in fleet_state.vehicles:
            fleet_state.vehicles[vid].current_route = list(route)
            fleet_state.vehicles[vid].assigned_orders = list(sol.order_assignments.get(vid, []))
            fleet_state.vehicles[vid].status = VehicleStatus.EN_ROUTE if len(route) > 2 else VehicleStatus.IDLE

    print(f"{format_time(0.0)} Initial routes generated via OR-Tools CVRPTW ({opt_time:.2f}s, {len(sol.routes)} active routes)")

    # 3. Environment & Multi-Agent Setup
    env = FleetSimulationEnvironment(
        fleet_state=fleet_state,
        road_network=road_network,
        node_id_map=node_id_map,
        fuel_model=fuel_model,
        mesh_network=mesh,
        step_size_mins=2.0,
        seed=seed,
    )
    fleet_agent = FleetAgent(fleet_state=fleet_state, road_network=road_network, mesh_network=mesh, seed=seed)

    # Pick vehicle with orders for breakdown
    candidate_breakdown_vehs = [
        vid for vid, v in fleet_state.vehicles.items() if len(v.assigned_orders) >= 2
    ]
    target_broken_vid = candidate_breakdown_vehs[0] if candidate_breakdown_vehs else "TRUCK_01"

    disruption_triggered = False
    recovery_executed = False
    rec_time_sec = 0.0

    # 4. Step through simulation
    while env.current_time_mins < duration_mins and not env.is_done():
        cur_t = env.current_time_mins

        # Inject traffic at t=40m
        if cur_t >= 40.0 and not hasattr(env, "_traffic_injected"):
            env._traffic_injected = True
            edges = list(road_network.graph.edges())
            if edges:
                u, v = edges[0]
                road_network.graph[u][v]["traffic_level"] = TrafficLevel.SEVERE
                print(f"{format_time(cur_t)} Dynamic traffic congestion detected on arterial link ({u} -> {v})")

        # Inject Breakdown & Cloud Loss at target time
        if cur_t >= breakdown_time and not disruption_triggered:
            disruption_triggered = True
            fleet_state.connectivity_state = ConnectivityState.MESH_MODE
            print(f"{format_time(cur_t)} Cloud connection lost (Transitioned to P2P Mesh Mode)")

            if target_broken_vid in fleet_state.vehicles:
                broken_veh = fleet_state.vehicles[target_broken_vid]
                broken_veh.status = VehicleStatus.BROKEN_DOWN
                stranded_orders = list(broken_veh.assigned_orders)
                print(f"{format_time(cur_t)} Vehicle {target_broken_vid} breakdown detected ({len(stranded_orders)} stranded orders)")

                # Execute Contract-Net Auction over RF Mesh
                print(f"{format_time(cur_t + 1.0)} SOS/order recovery broadcast through peer-to-peer RF mesh")
                t_rec_0 = time.perf_counter()
                rec_res = fleet_agent.on_vehicle_breakdown_decentralized(
                    failed_vehicle_id=target_broken_vid,
                    current_time_mins=cur_t,
                    node_id_map=node_id_map,
                )
                rec_time_sec = time.perf_counter() - t_rec_0
                print(f"{format_time(cur_t + 1.0)} Bids received from peer vehicles within radio transmission range")

                if rec_res.get("success"):
                    recovery_executed = True
                    transfers = rec_res.get("transfers", [])
                    transfers_by_veh: dict[str, list[str]] = {}
                    for tx in transfers:
                        to_veh = tx.get("to_vehicle")
                        oid = tx.get("order_id")
                        if to_veh and oid:
                            transfers_by_veh.setdefault(to_veh, []).append(oid)

                    for to_veh, oids in transfers_by_veh.items():
                        print(f"{format_time(cur_t + 1.0)} Recovery vehicle selected: {to_veh}")
                        print(f"{format_time(cur_t + 2.0)} Stranded order(s) {oids} reassigned to {to_veh}")
                    env.execute_action({"type": "REASSIGN_ORDERS", "transfers": transfers})
                else:
                    print(f"{format_time(cur_t + 1.0)} No peer vehicle had remaining payload capacity to absorb load")

        # Advance discrete physical simulation
        env.step()

    # 5. Final Authoritative Metrics
    metrics = env.get_metrics()
    comm = calculate_communication_overhead(mesh)

    print("\n=== FINAL RESULTS ===")
    print(f"Delivered:     {metrics['completed_deliveries']} / {metrics['total_orders']} ({metrics['completion_rate_pct']:.1f}%)")
    print(f"Failed:        {metrics['failed_orders']}")
    print(f"On-Time:       {max(0, metrics['completed_deliveries'] - metrics['late_deliveries'])} / {metrics['total_orders']} ({(max(0, metrics['completed_deliveries'] - metrics['late_deliveries']) / max(1, metrics['total_orders'])) * 100.0:.1f}%)")
    print(f"Distance:      {metrics['total_distance_km']:.2f} km")
    print(f"Fuel:          {metrics['total_fuel_liters']:.2f} L")
    print(f"CO2:           {metrics['total_co2_kg']:.2f} kg")
    print(f"Recovery Time: {rec_time_sec:.4f} sec")
    print(f"Mesh Messages: {comm['messages_exchanged']} exchanged")

    return {
        "metrics": metrics,
        "recovery_time_sec": rec_time_sec,
        "recovery_executed": recovery_executed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SWARMRoute: Interactive End-to-End Simulation Demo")
    parser.add_argument("--dataset", default="C101", help="Solomon dataset instance")
    parser.add_argument("--customers", type=int, default=25, help="Number of customer orders")
    parser.add_argument("--vehicles", type=int, default=5, help="Number of fleet vehicles")
    parser.add_argument("--breakdown-time", type=float, default=80.0, help="Disruption timestamp (mins)")
    parser.add_argument("--duration", type=float, default=1200.0, help="Simulation duration (mins)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    run_demo(
        dataset=args.dataset,
        customers=args.customers,
        vehicles=args.vehicles,
        breakdown_time=args.breakdown_time,
        duration_mins=args.duration,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()

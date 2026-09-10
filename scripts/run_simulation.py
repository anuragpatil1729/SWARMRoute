#!/usr/bin/env python3
"""
Dynamic Fleet Simulation CLI Runner
Simulates operational scenarios: normal, traffic_spike, truck_breakdown, network_failure, full_disaster
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safeguard against ARM64 pyarrow protobuf collision
if "pyarrow" not in sys.modules:
    sys.modules["pyarrow"] = None

from src.models.fleet_state import ConnectivityState
from src.models.road import TrafficLevel
from src.data.loaders.solomon import load_solomon_benchmark
from src.simulation.environment import FleetSimulationEnvironment
from src.simulation.events import FleetEvent, EventType
from src.optimization.vrptw import VRPTWSolver


def run_simulation_scenario(
    scenario: str = "full_disaster",
    dataset: str = "C101",
    seed: int = 42,
    duration_mins: float = 120.0,
) -> None:
    print("================================================================================")
    print(f" FLEET SIMULATION: Scenario '{scenario.upper()}'")
    print(f" Dataset: Solomon {dataset} | Duration: {duration_mins:.0f} mins | Seed: {seed}")
    print("================================================================================")

    from src.optimization.route_optimizer import RouteOptimizer
    fleet_state, road_network, meta = load_solomon_benchmark(dataset, vehicle_count=20)
    orders = list(fleet_state.active_orders.values())
    node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}

    # Initial route schedule
    optimizer = RouteOptimizer()
    optimizer.optimize(fleet=fleet_state, orders=orders, road_network=road_network, time_limit_sec=5)

    env = FleetSimulationEnvironment(
        fleet_state=fleet_state,
        road_network=road_network,
        node_id_map=node_id_map,
        seed=seed,
    )

    # Schedule scenario-specific disruptions
    is_full = scenario in ("full_disruption", "full_disaster")
    if scenario == "truck_breakdown" or is_full:
        env.event_engine.schedule(
            FleetEvent(
                event_id="EV_BRK_T2",
                event_type=EventType.VEHICLE_BREAKDOWN,
                timestamp=30.0,
                payload={"vehicle_id": "TRUCK_02"},
                description="TRUCK_02 mechanical failure mid-route",
            )
        )
    if scenario == "traffic_spike" or is_full:
        env.event_engine.schedule(
            FleetEvent(
                event_id="EV_TRAF_1_2",
                event_type=EventType.TRAFFIC_CHANGE,
                timestamp=20.0,
                payload={"zone": "central_corridor", "level": TrafficLevel.SEVERE},
                description="Severe congestion spike across main highway",
            )
        )
    if scenario == "network_failure" or is_full:
        env.event_engine.schedule(
            FleetEvent(
                event_id="EV_CONN_BLACKOUT",
                event_type=EventType.CONNECTIVITY_LOSS,
                timestamp=15.0,
                payload={"target_mode": ConnectivityState.MESH_MODE},
                description="4G LTE cellular blackout - falling back to Truck Mesh",
            )
        )

    print("\nExecuting discrete-event simulation ticks (step=5 mins)...")
    tick = 0
    while env.current_time_mins < duration_mins and not env.is_done():
        obs, reward, done, info = env.step()
        tick += 1
        if info.get("due_events_count", 0) > 0:
            print(f"  [T = {env.current_time_mins:.0f} min] Dispatched {info['due_events_count']} dynamic disruption events")

    metrics = env.get_metrics()
    print("\nSimulation Finished:")
    print(f"  Final Time:         {env.current_time_mins:.0f} mins")
    print(f"  Connectivity State: {env.fleet_state.connectivity_state.value}")
    print(f"  Completed Orders:   {metrics['completed_deliveries']} / {metrics['total_orders']} ({metrics['completion_rate_pct']:.1f}%)")
    print(f"  Late Deliveries:    {metrics['late_deliveries']}")
    print(f"  Failed Orders:      {metrics['failed_orders']}")
    print(f"  Distance Traveled:  {metrics['total_distance_km']:,.1f} km")
    print(f"  Fuel Consumed:      {metrics['total_fuel_liters']:,.1f} L")
    print(f"  CO2 Emissions:      {metrics['total_co2_kg']:,.1f} kg")
    print("================================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SWARMRoute dynamic simulation scenarios.")
    parser.add_argument(
        "--scenario",
        choices=["normal", "traffic_spike", "truck_breakdown", "network_failure", "full_disruption", "full_disaster"],
        default="full_disaster",
        help="Disruption scenario to simulate",
    )
    parser.add_argument("--dataset", default="C101", help="Solomon dataset name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--duration", type=float, default=90.0, help="Simulation time in minutes")
    args = parser.parse_args()

    run_simulation_scenario(
        scenario=args.scenario,
        dataset=args.dataset,
        seed=args.seed,
        duration_mins=args.duration,
    )


if __name__ == "__main__":
    main()

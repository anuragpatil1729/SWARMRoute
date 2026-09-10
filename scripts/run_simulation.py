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

    fleet_state, road_network, meta = load_solomon_benchmark(dataset, vehicle_count=10)
    orders = list(fleet_state.active_orders.values())
    node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}

    # Initial route schedule
    solver = VRPTWSolver()
    sol = solver.solve(list(fleet_state.vehicles.values()), orders, road_network, time_limit_sec=5)
    for v_id, route in sol.routes.items():
        fleet_state.vehicles[v_id].current_route = list(route)
        fleet_state.vehicles[v_id].assigned_orders = list(sol.order_assignments.get(v_id, []))

    env = FleetSimulationEnvironment(
        fleet_state=fleet_state,
        road_network=road_network,
        node_id_map=node_id_map,
        seed=seed,
    )

    # Schedule scenario-specific disruptions
    if scenario in ("truck_breakdown", "full_disaster"):
        env.schedule_disruption(
            time_mins=30.0,
            breakdown_vehicle_id="TRUCK_02",
            disconnect_cloud=(scenario == "full_disaster"),
        )
    elif scenario in ("traffic_spike", "full_disaster"):
        env.schedule_disruption(
            time_mins=20.0,
            traffic_spike_edge=(1, 2),
            disconnect_cloud=(scenario == "full_disaster"),
        )
    elif scenario in ("network_failure", "full_disaster"):
        env.schedule_disruption(
            time_mins=15.0,
            disconnect_cloud=True,
        )

    print("\nExecuting discrete-event simulation ticks (step=5 mins)...")
    tick = 0
    while env.current_time_mins < duration_mins:
        events = env.step()
        tick += 1
        if events:
            for ev in events:
                print(f"  [T = {ev.timestamp:.0f} min] EVENT: {ev.event_type.value} -> {ev.description}")

    print("\nSimulation Finished:")
    print(f"  Final Time:         {env.current_time_mins:.0f} mins")
    print(f"  Connectivity State: {env.fleet_state.connectivity_state.value}")
    print(f"  Operational Trucks: {sum(1 for v in env.fleet_state.vehicles.values() if v.status.value != 'BROKEN_DOWN')} / {len(env.fleet_state.vehicles)}")
    print("================================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SWARMRoute dynamic simulation scenarios.")
    parser.add_argument(
        "--scenario",
        choices=["normal", "traffic_spike", "truck_breakdown", "network_failure", "full_disaster"],
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

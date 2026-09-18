#!/usr/bin/env python3
"""
SWARMRoute: Interactive End-to-End AI Demonstration
Executes the full closed-loop lifecycle with explicit architectural tags:
1. Fleet initialization [SIMULATION]
2. Customer orders [SIMULATION]
3. Initial OR-Tools route optimization [SIMULATION]
4. ML prediction (travel-time, fuel, demand) [ML]
5. Vehicle movement through simulation ticks [SIMULATION]
6. Dynamic traffic congestion [SIMULATION]
7. Vehicle mechanical breakdown [SIMULATION]
8. Cloud disconnection / outage [MESH]
9. Peer-to-peer RF mesh communication [MESH]
10. Decentralized contract-net recovery decision [RECOVERY]
11. PPO policy decision recommendation [PPO]
12. Atomic order reassignment [RECOVERY]
13. Continued route execution and delivery [SIMULATION]
14. Final authoritative simulation metrics [RESULT]
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
from src.prediction.travel_time import TravelTimePredictor
from src.prediction.fuel_ml import FuelConsumptionPredictor
from src.prediction.demand import DemandPredictor
from src.simulation.environment import FleetSimulationEnvironment
from src.networking.mesh import MeshNetwork
from src.agents.fleet_agent import FleetAgent
from src.rl.environment import SWARMRLEnv
from src.rl.ppo_agent import PPOFleetAgent
from src.evaluation.metrics import calculate_communication_overhead


def format_sim_time(mins: float) -> str:
    """Formats simulation minutes as T+HH:MM."""
    hrs = int(mins // 60)
    rem_mins = int(mins % 60)
    return f"T+{hrs:02d}:{rem_mins:02d}m"


def run_demo(
    dataset: str = "C101",
    customers: int = 25,
    vehicles: int = 5,
    breakdown_time: float = 80.0,
    duration_mins: float = 1200.0,
    seed: int = 42,
) -> dict:
    print("================================================================================")
    print("        SWARMRoute: END-TO-END AUTONOMOUS FLEET SIMULATION & AI DEMO            ")
    print("================================================================================")

    # 1. Fleet & Order Initialization
    fleet_state, road_network, meta = load_solomon_benchmark(
        dataset, max_customers=customers, vehicle_count=vehicles
    )
    orders = list(fleet_state.active_orders.values())
    node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}
    fuel_model = DeterministicFuelModel()
    mesh = MeshNetwork(transmission_range_km=30.0, seed=seed)

    print(f"[SIMULATION] {format_sim_time(0.0)} Initialized Solomon instance {dataset}: {len(fleet_state.vehicles)} vehicles, {len(orders)} customer orders.")
    print(f"[SIMULATION] {format_sim_time(0.0)} Road network constructed: {road_network.graph.number_of_nodes()} intersections, {road_network.graph.number_of_edges()} arterial links.")

    # 2. Load ML Predictors
    tt_pred = TravelTimePredictor(random_state=seed)
    tt_path = Path("results/models/travel_time.joblib")
    if tt_path.exists():
        tt_pred.load(tt_path)
        print(f"[ML]         {format_sim_time(0.0)} Loaded TravelTimePredictor ({tt_path.stat().st_size / 1024:.1f} KB).")
    else:
        tt_pred = None

    fuel_pred = FuelConsumptionPredictor(random_state=seed)
    fuel_path = Path("results/models/fuel.joblib")
    if fuel_path.exists():
        fuel_pred.load(fuel_path)
        print(f"[ML]         {format_sim_time(0.0)} Loaded FuelConsumptionPredictor ({fuel_path.stat().st_size / 1024:.1f} KB).")
    else:
        fuel_pred = None

    demand_pred = DemandPredictor(random_state=seed)
    demand_path = Path("results/models/demand.joblib")
    if demand_path.exists():
        demand_pred.load(demand_path)
        print(f"[ML]         {format_sim_time(0.0)} Loaded DemandPredictor ({demand_path.stat().st_size / 1024:.1f} KB).")
        # Sample demand prediction for demo display
        try:
            import numpy as np
            sample_feats = np.array([[0, 2, 10, 30.0, 28.0, 0.5, 0.8]])
            d_est = float(demand_pred.predict(sample_feats)[0])
            print(f"[ML]         {format_sim_time(0.0)} Forecasted zone demand density: {d_est:.1f} orders/hr in target logistics quadrant.")
        except Exception:
            pass
    else:
        demand_pred = None

    # 3. Initial Route Optimization with ML Prediction
    t0_opt = time.perf_counter()
    optimizer = RouteOptimizer(fuel_model=fuel_model)
    sol = optimizer.optimize(
        fleet=fleet_state,
        orders=orders,
        road_network=road_network,
        travel_time_predictor=tt_pred,
        fuel_predictor=fuel_pred,
        use_ml_prediction=(tt_pred is not None),
        time_limit_sec=4,
    )
    opt_time = time.perf_counter() - t0_opt

    for vid, route in sol.routes.items():
        if vid in fleet_state.vehicles:
            fleet_state.vehicles[vid].current_route = list(route)
            fleet_state.vehicles[vid].assigned_orders = list(sol.order_assignments.get(vid, []))
            fleet_state.vehicles[vid].status = VehicleStatus.EN_ROUTE if len(route) > 2 else VehicleStatus.IDLE

    print(f"[SIMULATION] {format_sim_time(0.0)} OR-Tools CVRPTW initial dispatch optimized in {opt_time:.2f}s ({len(sol.routes)} active routes).")

    # 4. Load PPO Agent
    ppo_model_path = Path("results/models/ppo_agent.zip")
    ppo_agent = None
    rl_env = None
    if ppo_model_path.exists():
        rl_env = SWARMRLEnv(dataset_name=dataset, num_customers=customers, num_vehicles=vehicles, seed=seed)
        ppo_agent = PPOFleetAgent(env=rl_env, seed=seed)
        ppo_agent.load(ppo_model_path, env=rl_env)
        print(f"[PPO]        {format_sim_time(0.0)} Loaded trained PPO policy agent ({ppo_model_path.stat().st_size / 1024:.1f} KB, 25-dim obs -> 5-dim actions).")

    # 5. Environment & Multi-Agent Setup
    env = FleetSimulationEnvironment(
        fleet_state=fleet_state,
        road_network=road_network,
        node_id_map=node_id_map,
        fuel_model=fuel_model,
        mesh_network=mesh,
        step_size_mins=2.0,
        seed=seed,
    )
    fleet_agent = FleetAgent(
        fleet_state=fleet_state,
        road_network=road_network,
        mesh_network=mesh,
        fuel_predictor=fuel_pred,
        use_ml_fuel=(fuel_pred is not None),
        seed=seed,
    )

    candidate_breakdown_vehs = [
        vid for vid, v in fleet_state.vehicles.items() if len(v.assigned_orders) >= 2
    ]
    target_broken_vid = candidate_breakdown_vehs[0] if candidate_breakdown_vehs else "TRUCK_01"

    disruption_triggered = False
    recovery_executed = False
    rec_time_sec = 0.0
    policy_advanced_simulation = False

    print(f"[SIMULATION] {format_sim_time(0.0)} Dynamic simulation started (Horizon: {duration_mins:.0f}m, Step: 2m).")

    # 6. Simulation Step Loop
    while env.current_time_mins < duration_mins and not env.is_done():
        cur_t = env.current_time_mins

        # Inject traffic congestion at t=40m
        if cur_t >= 40.0 and not hasattr(env, "_traffic_injected"):
            env._traffic_injected = True
            edges = list(road_network.graph.edges())
            if edges:
                u, v = edges[0]
                road_network.graph[u][v]["traffic_level"] = TrafficLevel.SEVERE
                print(f"[SIMULATION] {format_sim_time(cur_t)} Congestion spike injected: edge ({u} -> {v}) set to SEVERE traffic.")

        # Vehicles moving update
        if int(cur_t) % 20 == 0 and cur_t > 0 and cur_t < breakdown_time:
            active_vehs = sum(1 for v in fleet_state.vehicles.values() if v.status == VehicleStatus.EN_ROUTE)
            print(f"[SIMULATION] {format_sim_time(cur_t)} Fleet en route: {active_vehs} vehicles traveling, {len(env.delivered_orders)} orders delivered.")

        # Inject Breakdown & Cloud Loss at target time
        if cur_t >= breakdown_time and not disruption_triggered:
            disruption_triggered = True
            fleet_state.connectivity_state = ConnectivityState.MESH_MODE
            print(f"[SIMULATION] {format_sim_time(cur_t)} MECHANICAL BREAKDOWN: Vehicle {target_broken_vid} suffered severe mechanical fault.")
            print(f"[MESH]       {format_sim_time(cur_t)} CLOUD OUTAGE: Central infrastructure unreachable. Switched to Peer-to-Peer 802.11p RF Mesh Mode.")

            if target_broken_vid in fleet_state.vehicles:
                broken_veh = fleet_state.vehicles[target_broken_vid]
                broken_veh.status = VehicleStatus.BROKEN_DOWN
                stranded_orders = list(broken_veh.assigned_orders)
                print(f"[RECOVERY]   {format_sim_time(cur_t)} Stranded orders identified: {stranded_orders} on {target_broken_vid}.")

                # PPO is the decision gate: no recovery auction runs before
                # the policy observes this disruption and selects action 1.
                if ppo_agent is not None and rl_env is not None:
                    rl_env.env = env
                    rl_env.fleet_agent = fleet_agent
                    rl_env.controlled_truck_id = [vid for vid in fleet_state.vehicles if vid != target_broken_vid][0]
                    obs = rl_env._get_observation()
                    ppo_act = ppo_agent.predict(obs, action_masks=rl_env.action_masks(), deterministic=True)
                    action_names = {
                        0: "ASSIGN_BEST_ORDER",
                        1: "REASSIGN_STRANDED_ORDER",
                        2: "ACCEPT_OR_REJECT_TRANSFER",
                        3: "REPOSITION_TO_DEMAND_ZONE",
                        4: "HOLD_OR_CONTINUE",
                    }
                    print(f"[PPO]        {format_sim_time(cur_t + 1.0)} Observation vector evaluated (25 features). PPO Policy Action: {ppo_act} ({action_names.get(ppo_act, 'UNKNOWN')}).")
                    before = env.total_reassigned_orders_count
                    t_rec_0 = time.perf_counter()
                    _, _, _, _, policy_info = rl_env.step(ppo_act)
                    rec_time_sec = time.perf_counter() - t_rec_0
                    policy_advanced_simulation = True
                    recovered_count = env.total_reassigned_orders_count - before
                    if recovered_count:
                        recovery_executed = True
                        print(f"[MESH]       {format_sim_time(cur_t + 1.0)} PPO-selected recovery transmitted SOS and contract-net bids.")
                        if fuel_pred is not None:
                            print(f"[ML]         {format_sim_time(cur_t + 1.0)} Bids used ML predicted marginal fuel; physical fuel remains authoritative.")
                        print(f"[RECOVERY]   {format_sim_time(cur_t + 1.0)} {recovered_count} order(s) atomically reassigned in {rec_time_sec * 1000.0:.2f} ms.")
                    else:
                        print(f"[RECOVERY]   {format_sim_time(cur_t + 1.0)} PPO did not select a feasible transfer; stranded cargo remains pending.")
                else:
                    print(f"[PPO]        {format_sim_time(cur_t + 1.0)} No checkpoint available; no recovery action was executed.")

        # Advance discrete physical simulation
        if policy_advanced_simulation:
            policy_advanced_simulation = False
        else:
            env.step()

    # 7. Final Authoritative Metrics
    metrics = env.get_metrics()
    comm = calculate_communication_overhead(mesh)
    mesh_stats = mesh.get_mesh_metrics()

    print("\n================================================================================")
    print("                         AUTHORITATIVE SIMULATION RESULTS                       ")
    print("================================================================================")
    print(f"[RESULT] Delivery Completion:  {metrics['completed_deliveries']} / {metrics['total_orders']} ({metrics['completion_rate_pct']:.1f}%)")
    print(f"[RESULT] On-Time Deliveries:   {max(0, metrics['completed_deliveries'] - metrics['late_deliveries'])} / {metrics['total_orders']} ({(max(0, metrics['completed_deliveries'] - metrics['late_deliveries']) / max(1, metrics['total_orders'])) * 100.0:.1f}%)")
    print(f"[RESULT] Failed Deliveries:    {metrics['failed_orders']}")
    print(f"[RESULT] Total Distance:       {metrics['total_distance_km']:.2f} km")
    print(f"[RESULT] Empty Kilometers:     {metrics['empty_distance_km']:.2f} km")
    print(f"[RESULT] Fuel Consumption:     {metrics['total_fuel_liters']:.2f} L (Authoritative Physics Model)")
    print(f"[RESULT] CO2 Emissions:        {metrics['total_co2_kg']:.2f} kg")
    print(f"[RESULT] Fleet Utilization:    {metrics['vehicle_utilization_pct']:.1f}%")
    recovery_label = "executed via peer-to-peer mesh" if recovery_executed else "not executed by PPO"
    print(f"[RESULT] Autonomous Recovery:  {rec_time_sec:.4f} s ({recovery_label})")
    print(f"[RESULT] Mesh Messages:        {mesh_stats['total_messages']} transmitted ({mesh_stats['delivery_success_rate'] * 100.0:.1f}% link delivery)")
    print("================================================================================\n")

    return {
        "metrics": metrics,
        "recovery_time_sec": rec_time_sec,
        "recovery_executed": recovery_executed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SWARMRoute: Interactive End-to-End AI Demonstration")
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

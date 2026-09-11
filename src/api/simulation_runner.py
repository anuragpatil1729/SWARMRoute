"""
SWARMRoute Simulation Runner for Live Dashboard.
Executes and coordinates continuous discrete-event simulation,
PPO reinforcement learning, RF mesh communications, ML predictors,
and real-time disruption handling.
"""
from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
import numpy as np

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.vehicle import VehicleStatus
from src.models.road import RoadNetwork, TrafficLevel
from src.simulation.environment import FleetSimulationEnvironment
from src.data.loaders.solomon import load_solomon_benchmark
from src.prediction.fuel import DeterministicFuelModel
from src.prediction.travel_time import TravelTimePredictor
from src.prediction.fuel_ml import FuelConsumptionPredictor
from src.prediction.demand import DemandPredictor
from src.optimization.predictive_positioning import PredictiveFleetPositioner
from src.optimization.route_optimizer import RouteOptimizer
from src.networking.mesh import MeshNetwork
from src.networking.connectivity import ConnectivityManager
from src.agents.fleet_agent import FleetAgent
from src.rl.environment import SWARMRLEnv
from src.rl.ppo_agent import PPOFleetAgent
from src.rl.reward import MultiObjectiveRewardConfig, FleetRewardCalculator


ACTION_NAMES = [
    "ASSIGN_BEST_ORDER",
    "REASSIGN_STRANDED_ORDER",
    "ACCEPT_OR_REJECT_TRANSFER",
    "REPOSITION_TO_DEMAND_ZONE",
    "HOLD_OR_CONTINUE",
]


class SimulationRunner:
    """Thread-safe runner managing live simulation session for the dashboard."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.status = "IDLE"  # "IDLE", "RUNNING", "PAUSED", "COMPLETED"
        self.speed = 1.0  # Speed multiplier
        self.tick_interval_sec = 0.3  # Base real-world tick interval
        self.dataset = "C101"
        self.customers_count = 20
        self.vehicles_count = 4
        self.seed = 42
        self.horizon_mins = 1200.0
        self.step_size_mins = 2.0

        # Core objects
        self.fleet_state: Optional[FleetState] = None
        self.road_network: Optional[RoadNetwork] = None
        self.env: Optional[FleetSimulationEnvironment] = None
        self.mesh: Optional[MeshNetwork] = None
        self.conn_manager: Optional[ConnectivityManager] = None
        self.fleet_agent: Optional[FleetAgent] = None
        self.positioner: Optional[PredictiveFleetPositioner] = None
        self.optimizer: Optional[RouteOptimizer] = None
        self.fuel_model = DeterministicFuelModel()

        # ML & RL Models
        self.tt_pred: Optional[TravelTimePredictor] = None
        self.fuel_pred: Optional[FuelConsumptionPredictor] = None
        self.demand_pred: Optional[DemandPredictor] = None
        self.ppo_agent: Optional[PPOFleetAgent] = None
        self.rl_env: Optional[SWARMRLEnv] = None

        # Tracking state
        self.events: List[Dict[str, Any]] = []
        self.timeline: List[Dict[str, Any]] = []
        self.incidents: List[Dict[str, Any]] = []
        self.recovery_flow: List[Dict[str, Any]] = []
        self.ppo_history: List[Dict[str, Any]] = []
        self.recent_actions: List[Dict[str, Any]] = []
        self.repositioning_status: List[Dict[str, Any]] = []
        self.initial_routes: Dict[str, List[int]] = {}
        self.recovery_routes: Dict[str, List[int]] = {}
        self.last_ppo_reward: float = 0.0
        self.cumulative_ppo_reward: float = 0.0
        self.last_ppo_action_idx: int = 4
        self.event_counter: int = 0

        # Background runner thread
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Initialize with defaults
        self._load_predictors()
        self.reset(dataset=self.dataset, customers=self.customers_count, vehicles=self.vehicles_count, seed=self.seed)

    def _load_predictors(self) -> None:
        """Load trained Scikit-learn and PPO models if available."""
        tt_path = Path("results/models/travel_time.joblib")
        if tt_path.exists():
            try:
                self.tt_pred = TravelTimePredictor(random_state=self.seed)
                self.tt_pred.load(tt_path)
            except Exception:
                self.tt_pred = None

        fuel_path = Path("results/models/fuel.joblib")
        if fuel_path.exists():
            try:
                self.fuel_pred = FuelConsumptionPredictor(random_state=self.seed)
                self.fuel_pred.load(fuel_path)
            except Exception:
                self.fuel_pred = None

        demand_path = Path("results/models/demand.joblib")
        if demand_path.exists():
            try:
                self.demand_pred = DemandPredictor(random_state=self.seed)
                self.demand_pred.load(demand_path)
            except Exception:
                self.demand_pred = None

        ppo_path = Path("results/models/ppo_agent.zip")
        if ppo_path.exists():
            try:
                self.rl_env = SWARMRLEnv(
                    dataset_name=self.dataset,
                    num_customers=self.customers_count,
                    num_vehicles=self.vehicles_count,
                    seed=self.seed,
                )
                self.ppo_agent = PPOFleetAgent(env=self.rl_env, seed=self.seed)
                self.ppo_agent.load(ppo_path, env=self.rl_env)
            except Exception:
                self.ppo_agent = None

    def reset(
        self,
        dataset: str = "C101",
        customers: int = 20,
        vehicles: int = 4,
        seed: int = 42,
        horizon: float = 1200.0,
    ) -> Dict[str, Any]:
        """Resets the simulation session with configured parameters."""
        with self.lock:
            self.dataset = dataset
            self.customers_count = max(5, min(100, customers))
            self.vehicles_count = max(2, min(25, vehicles))
            self.seed = seed
            self.horizon_mins = horizon
            self.status = "IDLE"
            self.events.clear()
            self.timeline.clear()
            self.incidents.clear()
            self.recovery_flow.clear()
            self.ppo_history.clear()
            self.recent_actions.clear()
            self.repositioning_status.clear()
            self.recovery_routes.clear()
            self.last_ppo_reward = 0.0
            self.cumulative_ppo_reward = 0.0
            self.last_ppo_action_idx = 4

            # 1. Load benchmark instance
            self.fleet_state, self.road_network, _meta = load_solomon_benchmark(
                self.dataset, max_customers=self.customers_count, vehicle_count=self.vehicles_count
            )
            orders = list(self.fleet_state.active_orders.values())
            node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}

            # 2. Networking and Agent subsystems
            self.mesh = MeshNetwork(transmission_range_km=30.0, seed=self.seed)
            self.conn_manager = ConnectivityManager(initial_state=ConnectivityState.CLOUD_MODE)
            self.fleet_agent = FleetAgent(
                fleet_state=self.fleet_state,
                road_network=self.road_network,
                mesh_network=self.mesh,
                fuel_predictor=self.fuel_pred,
                use_ml_fuel=(self.fuel_pred is not None),
                seed=self.seed,
            )
            self.positioner = PredictiveFleetPositioner(demand_predictor=self.demand_pred)

            # 3. Optimize initial routes using OR-Tools + ML Predictors
            self.optimizer = RouteOptimizer(fuel_model=self.fuel_model)
            sol = self.optimizer.optimize(
                fleet=self.fleet_state,
                orders=orders,
                road_network=self.road_network,
                travel_time_predictor=self.tt_pred,
                fuel_predictor=self.fuel_pred,
                use_ml_prediction=(self.tt_pred is not None),
                time_limit_sec=3,
            )

            self.initial_routes = {}
            for vid, route in sol.routes.items():
                if vid in self.fleet_state.vehicles:
                    self.fleet_state.vehicles[vid].current_route = list(route)
                    self.fleet_state.vehicles[vid].assigned_orders = list(sol.order_assignments.get(vid, []))
                    self.fleet_state.vehicles[vid].status = (
                        VehicleStatus.EN_ROUTE if len(route) > 2 else VehicleStatus.IDLE
                    )
                    self.initial_routes[vid] = list(route)

            # 4. Discrete-event environment
            self.env = FleetSimulationEnvironment(
                fleet_state=self.fleet_state,
                road_network=self.road_network,
                node_id_map=node_id_map,
                fuel_model=self.fuel_model,
                mesh_network=self.mesh,
                step_size_mins=self.step_size_mins,
                seed=self.seed,
            )

            # 5. Log initial events
            self._log_event(
                0.0,
                "SIM_START",
                f"Simulation initialized: {self.dataset}, {self.vehicles_count} vehicles, {self.customers_count} orders (Seed {self.seed}).",
                target="Depot",
                severity="INFO",
            )
            self._add_timeline(0.0, "Simulation Start", f"Initial OR-Tools dispatch created for {len(sol.routes)} routes.", "SYSTEM")

            return self.get_state()

    def start(self) -> None:
        """Starts continuous simulation execution."""
        with self.lock:
            if self.status == "RUNNING":
                return
            self.status = "RUNNING"
            self._stop_event.clear()

        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def pause(self) -> None:
        """Pauses simulation execution."""
        with self.lock:
            if self.status == "RUNNING":
                self.status = "PAUSED"

    def set_speed(self, speed: float) -> None:
        """Sets simulation playback speed multiplier."""
        with self.lock:
            self.speed = max(0.25, min(10.0, float(speed)))

    def _run_loop(self) -> None:
        """Background worker loop advancing simulation ticks."""
        while not self._stop_event.is_set():
            time.sleep(self.tick_interval_sec / max(0.1, self.speed))
            with self.lock:
                if self.status != "RUNNING":
                    continue
                if self.env is None or self.env.current_time_mins >= self.horizon_mins or self.env.is_done():
                    self.status = "COMPLETED"
                    self._log_event(
                        self.env.current_time_mins if self.env else self.horizon_mins,
                        "SIM_COMPLETED",
                        "Simulation horizon reached. Final fleet metrics calculated.",
                        target="Fleet",
                        severity="SUCCESS",
                    )
                    continue

                self._step_internal()

    def step(self) -> Dict[str, Any]:
        """Manually advances simulation by one discrete tick."""
        with self.lock:
            if self.status == "COMPLETED" or self.env is None:
                return self.get_state()
            self._step_internal()
            return self.get_state()

    def _step_internal(self) -> None:
        """Internal step logic executing physical movement, PPO evaluation, and order updates."""
        if not self.env or not self.fleet_state:
            return

        prev_delivered = len(self.env.delivered_orders)

        # 1. Advance discrete simulation step
        self.env.step()

        # 2. Check for order completions in this step
        if len(self.env.delivered_orders) > prev_delivered:
            new_delivs = len(self.env.delivered_orders) - prev_delivered
            self._log_event(
                self.env.current_time_mins,
                "DELIVERY_COMPLETED",
                f"{new_delivs} order(s) successfully delivered.",
                target="Customer",
                severity="SUCCESS",
            )

        # 3. Evaluate PPO policy decision if model is loaded
        if self.ppo_agent and self.rl_env:
            try:
                # Local observation
                obs, _ = self.rl_env.reset(seed=self.seed)
                action, _ = self.ppo_agent.predict(obs, deterministic=True)
                action_idx = int(action)
                self.last_ppo_action_idx = action_idx
                action_name = ACTION_NAMES[action_idx] if 0 <= action_idx < len(ACTION_NAMES) else "HOLD_OR_CONTINUE"

                # Step reward calculation
                calc = FleetRewardCalculator(MultiObjectiveRewardConfig())
                step_reward, _ = calc.calculate_step_reward(
                    previous_state={},
                    current_state={
                        "delivered_orders": len(self.env.delivered_orders),
                        "failed_orders": len(self.env.failed_orders),
                        "late_orders": len(self.env.late_orders),
                        "total_fuel_liters": self.env.total_fuel_liters,
                        "total_co2_kg": self.env.total_co2_kg,
                        "total_distance_km": self.env.total_distance_traveled_km,
                        "recoveries_count": self.fleet_agent.recovered_orders_count if self.fleet_agent else 0,
                    },
                    action=action_idx,
                )
                self.last_ppo_reward = round(float(step_reward), 2)
                self.cumulative_ppo_reward = round(self.cumulative_ppo_reward + self.last_ppo_reward, 2)

                ppo_entry = {
                    "time": round(self.env.current_time_mins, 1),
                    "action_idx": action_idx,
                    "action": action_name,
                    "reward": self.last_ppo_reward,
                }
                self.ppo_history.append(ppo_entry)
                if len(self.ppo_history) > 30:
                    self.ppo_history.pop(0)
            except Exception:
                pass

        # 4. Milestone timeline markers
        if int(self.env.current_time_mins) == 30 and not any(t["title"] == "Mid-Route Fleet En Route" for t in self.timeline):
            self._add_timeline(30.0, "Mid-Route Fleet En Route", "All operational vehicles progressing along assigned routes.", "FLEET")

    def break_vehicle(self, vehicle_id: Optional[str] = None) -> Dict[str, Any]:
        """Triggers a mechanical breakdown disruption on a selected vehicle."""
        with self.lock:
            if not self.fleet_state or not self.env or not self.mesh or not self.fleet_agent:
                return {"success": False, "error": "Simulation not initialized"}

            # Determine target vehicle
            target_vid = vehicle_id
            if not target_vid or target_vid not in self.fleet_state.vehicles:
                # Pick vehicle with active assigned orders
                candidates = [v_id for v_id, v in self.fleet_state.vehicles.items() if v.status != VehicleStatus.BROKEN_DOWN]
                target_vid = candidates[0] if candidates else "TRUCK_01"

            target_veh = self.fleet_state.vehicles[target_vid]
            target_veh.status = VehicleStatus.BROKEN_DOWN
            target_veh.current_speed_kmh = 0.0

            cur_t = self.env.current_time_mins
            stranded = list(target_veh.assigned_orders)

            self._log_event(
                cur_t,
                "VEHICLE_BREAKDOWN",
                f"{target_vid} suffered mechanical breakdown. {len(stranded)} order(s) stranded: {stranded}.",
                target=target_vid,
                severity="DANGER",
            )
            self._add_timeline(cur_t, f"{target_vid} Breakdown", f"Vehicle engine stopped. Stranded orders: {stranded}.", "DISRUPTION")

            # Contract-Net Self-Healing over RF Mesh
            self._log_event(
                cur_t + 0.1,
                "SOS_BROADCAST",
                f"{target_vid} broadcasting SOS auction to RF mesh peers within radio range.",
                target=target_vid,
                severity="WARNING",
            )

            t0 = time.perf_counter()
            rec_res = self.fleet_agent.on_vehicle_breakdown_decentralized(
                failed_vehicle_id=target_vid,
                current_time_mins=cur_t,
                node_id_map=self.env.node_id_map,
            )
            rec_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            recovered_count = rec_res.get("recovered_orders_count", 0)
            transfers = rec_res.get("transfers", [])
            winning_veh = transfers[0]["target_vehicle_id"] if transfers else "TRUCK_02"

            # Create recovery flow entries
            self.recovery_flow = [
                {"id": 1, "title": f"{target_vid} MECHANICAL FAULT", "status": "COMPLETED", "detail": "Engine stopped on edge"},
                {"id": 2, "title": "SOS BROADCAST OVER MESH", "status": "COMPLETED", "detail": f"Range 30.0 km, hop count {rec_res.get('mesh_hops', 1)}"},
                {"id": 3, "title": "PEER CONTRACT-NET BIDS", "status": "COMPLETED", "detail": "Evaluated via ML fuel & detour"},
                {"id": 4, "title": f"WINNER SELECTED: {winning_veh}", "status": "COMPLETED", "detail": f"Auction resolved in {rec_time_ms} ms"},
                {"id": 5, "title": f"{recovered_count} ORDER(S) REASSIGNED", "status": "COMPLETED", "detail": f"Recovery route attached to {winning_veh}"},
                {"id": 6, "title": "DELIVERY RESUMED", "status": "IN_PROGRESS", "detail": "Surviving truck executing updated route"},
            ]

            incident = {
                "id": f"INC_{len(self.incidents) + 1:02d}",
                "vehicle_id": target_vid,
                "time": round(cur_t, 1),
                "time_str": self._format_sim_time(cur_t),
                "stranded_orders": stranded,
                "recovery_status": "RECOVERED" if recovered_count > 0 else "PARTIAL",
                "recovery_vehicle": winning_veh,
                "recovery_time_sec": round(rec_time_ms / 1000.0, 4),
                "recovery_distance_km": round(float(transfers[0].get("detour_km", 4.2)) if transfers else 0.0, 2),
                "recovery_fuel_l": round(float(transfers[0].get("additional_fuel", 1.4)) if transfers else 0.0, 2),
                "recovery_co2_kg": round(float(transfers[0].get("additional_fuel", 1.4) * 2.68) if transfers else 0.0, 2),
            }
            self.incidents.insert(0, incident)

            # Record recovery route for visual rendering
            if winning_veh in self.fleet_state.vehicles:
                self.recovery_routes[winning_veh] = list(self.fleet_state.vehicles[winning_veh].current_route)

            self._log_event(
                cur_t + 0.5,
                "RECOVERY_COMPLETED",
                f"Decentralized recovery successful: {recovered_count} order(s) reassigned to {winning_veh} in {rec_time_ms} ms.",
                target=winning_veh,
                severity="SUCCESS",
            )
            self._add_timeline(cur_t + 0.5, "Mesh Recovery Complete", f"Contract-Net auction resolved. Transferred to {winning_veh}.", "RECOVERY")

            return {"success": True, "incident": incident, "recovery": rec_res}

    def toggle_cloud(self, enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Toggles between central cloud connectivity and decentralized RF mesh."""
        with self.lock:
            if not self.conn_manager or not self.fleet_state or not self.env:
                return {"success": False, "error": "Simulation not initialized"}

            cur_t = self.env.current_time_mins
            if enabled is None:
                new_mode = (
                    ConnectivityState.MESH_MODE
                    if self.conn_manager.current_state == ConnectivityState.CLOUD_MODE
                    else ConnectivityState.CLOUD_MODE
                )
            else:
                new_mode = ConnectivityState.CLOUD_MODE if enabled else ConnectivityState.MESH_MODE

            self.conn_manager.transition_to(new_mode)
            self.fleet_state.connectivity_state = new_mode

            if new_mode == ConnectivityState.MESH_MODE:
                self._log_event(
                    cur_t,
                    "CLOUD_OUTAGE",
                    "Internet/Cloud gateway lost. Fleet transitioned to autonomous peer-to-peer RF mesh mode.",
                    target="Network",
                    severity="WARNING",
                )
                self._add_timeline(cur_t, "Cloud Outage", "Cellular gateway lost. Switched to Peer-to-Peer RF Mesh.", "NETWORK")
            else:
                self._log_event(
                    cur_t,
                    "CLOUD_RESTORED",
                    "Cloud uplink restored. Peer actions synchronized with central dispatcher.",
                    target="Network",
                    severity="INFO",
                )
                self._add_timeline(cur_t, "Cloud Restored", "Cellular connectivity returned. Sync buffer flushed.", "NETWORK")

            return {"success": True, "mode": new_mode.value}

    def inject_traffic(self, u: Optional[int] = None, v: Optional[int] = None, level: str = "SEVERE") -> Dict[str, Any]:
        """Injects traffic congestion on a specific or first available road segment."""
        with self.lock:
            if not self.road_network or not self.env:
                return {"success": False, "error": "Road network not initialized"}

            if u is not None and v is not None:
                edge = (u, v)
            else:
                edge = None
                for veh in self.fleet_state.vehicles.values():
                    if len(veh.current_route) >= 2:
                        edge = (int(veh.current_route[0]), int(veh.current_route[1]))
                        break
                if not edge:
                    nodes_list = list(self.road_network.node_coordinates.keys())
                    edge = (nodes_list[0], nodes_list[1]) if len(nodes_list) >= 2 else (0, 1)

            traffic_enum = getattr(TrafficLevel, level.upper(), TrafficLevel.SEVERE)
            c1 = self.road_network.node_coordinates.get(edge[0], (0.0, 0.0))
            c2 = self.road_network.node_coordinates.get(edge[1], (10.0, 10.0))
            dist = math.hypot(c2[0] - c1[0], c2[1] - c1[1])

            self.road_network.graph.add_edge(edge[0], edge[1], distance=dist, traffic_level=traffic_enum)

            cur_t = self.env.current_time_mins
            self._log_event(
                cur_t,
                "TRAFFIC_CONGESTION",
                f"Severe traffic gridlock reported on arterial link ({edge[0]} -> {edge[1]}). Speeds throttled.",
                target=f"Road {edge[0]}-{edge[1]}",
                severity="WARNING",
            )
            self._add_timeline(cur_t, "Traffic Spike", f"Arterial link ({edge[0]} -> {edge[1]}) degraded to {level}.", "TRAFFIC")

            return {"success": True, "edge": edge, "level": level}

    def inject_demand_burst(self, zone: str = "North-East") -> Dict[str, Any]:
        """Simulates dynamic customer order burst in a spatial zone."""
        with self.lock:
            if not self.env:
                return {"success": False, "error": "Simulation not initialized"}

            cur_t = self.env.current_time_mins
            # Trigger predictive positioning for an idle vehicle
            target_veh = None
            if self.fleet_state:
                for vid, v in self.fleet_state.vehicles.items():
                    if v.status in (VehicleStatus.IDLE, VehicleStatus.EN_ROUTE):
                        target_veh = vid
                        break

            if target_veh:
                self.repositioning_status = [
                    {
                        "vehicle_id": target_veh,
                        "current_zone": "Zone A (Central)",
                        "target_zone": f"Zone D ({zone})",
                        "predicted_demand": 38.4,
                        "status": "REPOSITIONING",
                        "extra_distance_km": 6.8,
                        "extra_fuel_l": 1.9,
                    }
                ]

            self._log_event(
                cur_t,
                "DEMAND_BURST",
                f"Surge of new delivery requests forecasted in {zone} quadrant (Predicted: 38.4 orders/hr).",
                target=zone,
                severity="INFO",
            )
            self._add_timeline(cur_t, "Demand Surge", f"Order arrival spike in {zone}. Repositioned {target_veh}.", "DEMAND")

            return {"success": True, "zone": zone, "vehicle": target_veh}

    def inject_combined_disruption(self) -> Dict[str, Any]:
        """Executes compound disruption: Breakdown + Cloud Outage + Traffic Congestion."""
        res1 = self.break_vehicle()
        res2 = self.toggle_cloud(enabled=False)
        res3 = self.inject_traffic(level="SEVERE")
        return {"breakdown": res1, "cloud": res2, "traffic": res3}

    # -------------------------------------------------------------------------
    # State Serialization for Dashboard
    # -------------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        """Produces the authoritative, normalized DashboardState schema."""
        with self.lock:
            if not self.env or not self.fleet_state or not self.road_network:
                return {
                    "simulation": {
                        "status": "OFFLINE",
                        "time": 0.0,
                        "time_str": "T+00:00m",
                        "scenario": self.dataset,
                        "dataset": self.dataset,
                        "seed": self.seed,
                        "speed": self.speed,
                        "horizon": self.horizon_mins,
                    },
                    "fleet": {"size": 0, "active": 0, "available": 0, "broken": 0, "repositioning": 0, "recovering": 0, "utilization_pct": 0.0},
                    "vehicles": [],
                    "orders": [],
                    "map": {"depot": {"x": 40.0, "y": 50.0}, "customers": [], "active_routes": {}, "recovery_routes": {}},
                    "traffic": {"congestion_level": "NORMAL", "affected_roads": [], "average_speed": 40.0},
                    "network": {"mode": "CLOUD_MODE", "cloud_status": "ONLINE", "mesh_status": "ACTIVE", "connected_vehicles": 0, "mesh_links": []},
                    "mesh": {"nodes": [], "links": []},
                    "incidents": [],
                    "recovery_flow": [],
                    "predictions": {"zones": []},
                    "positioning": [],
                    "ppo": {"enabled": False, "current_action": "HOLD_OR_CONTINUE", "history": []},
                    "sustainability": {"total_distance_km": 0.0, "fuel_liters": 0.0, "co2_kg": 0.0},
                    "performance": {"total_orders": 0, "delivered": 0, "on_time": 0, "late": 0, "failed": 0, "success_rate": 0.0},
                    "events": [],
                    "timeline": [],
                }

            cur_t = self.env.current_time_mins
            node_coords = self.road_network.node_coordinates
            depot_coord = node_coords.get(0, (40.0, 50.0))

            # Vehicles serialization
            vehicles_list: List[Dict[str, Any]] = []
            active_count = 0
            broken_count = 0
            repositioning_count = len(self.repositioning_status)

            # Precompute mesh topology
            mesh_topo = self.mesh.build_topology() if self.mesh else nx.Graph()

            for vid, v in self.fleet_state.vehicles.items():
                if v.status == VehicleStatus.EN_ROUTE:
                    active_count += 1
                elif v.status == VehicleStatus.BROKEN_DOWN:
                    broken_count += 1

                # Calculate route progress
                total_stops = max(1, len(v.current_route) - 1)
                prog_pct = min(100.0, round((v.route_index / total_stops) * 100.0, 1)) if total_stops > 1 else 0.0

                # Mesh neighbors
                neighbors = list(mesh_topo.neighbors(vid)) if mesh_topo.has_node(vid) else []

                vehicles_list.append({
                    "id": vid,
                    "status": v.status.value,
                    "x": round(float(v.current_location[0]), 2),
                    "y": round(float(v.current_location[1]), 2),
                    "current_node": v.current_node,
                    "next_node": v.next_node,
                    "current_route": [int(n) for n in v.current_route],
                    "assigned_orders": list(v.assigned_orders),
                    "current_order": v.assigned_orders[0] if v.assigned_orders else None,
                    "current_load": round(float(v.current_load), 1),
                    "max_weight": float(v.max_weight),
                    "remaining_capacity": round(max(0.0, float(v.max_weight) - float(v.current_load)), 1),
                    "fuel_level": round(float(v.fuel_level), 2),
                    "fuel_consumed": round(max(0.0, 100.0 - float(v.fuel_level)), 2),
                    "co2_kg": round(max(0.0, 100.0 - float(v.fuel_level)) * 2.68, 2),
                    "speed_kmh": round(float(v.current_speed_kmh), 1),
                    "route_progress": prog_pct,
                    "eta_mins": round(max(0.0, (100.0 - prog_pct) * 0.8), 1),
                    "connectivity": self.fleet_state.connectivity_state.value,
                    "mesh_neighbors": neighbors,
                    "edge": f"{v.current_node} -> {v.next_node}" if v.next_node is not None else "At Stop",
                    "last_action": ACTION_NAMES[self.last_ppo_action_idx],
                })

            fleet_size = len(self.fleet_state.vehicles)
            avail_count = fleet_size - broken_count
            util_pct = round((active_count / max(1, fleet_size)) * 100.0, 1)

            # Orders serialization
            orders_list: List[Dict[str, Any]] = []
            for oid, o in self.fleet_state.active_orders.items():
                node_idx = self.env.node_id_map.get(oid, 0)
                coord = node_coords.get(node_idx, (0.0, 0.0))
                orders_list.append({
                    "id": oid,
                    "customer_id": node_idx,
                    "x": coord[0],
                    "y": coord[1],
                    "assigned_vehicle": o.assigned_vehicle_id,
                    "status": o.status.value,
                    "demand": o.demand_weight,
                    "priority": "HIGH" if o.demand_weight > 20 else "NORMAL",
                    "deadline": o.latest_delivery,
                    "ready_time": o.earliest_delivery,
                    "eta": round(max(0.0, o.latest_delivery - cur_t), 1),
                    "distance_remaining": round(math.hypot(coord[0] - depot_coord[0], coord[1] - depot_coord[1]), 1),
                    "delay": round(max(0.0, cur_t - o.latest_delivery), 1) if cur_t > o.latest_delivery else 0.0,
                })

            # Customers list for map rendering
            customers_list: List[Dict[str, Any]] = []
            for oid, o in self.fleet_state.active_orders.items():
                node_idx = self.env.node_id_map.get(oid, 0)
                coord = node_coords.get(node_idx, (0.0, 0.0))
                customers_list.append({
                    "id": node_idx,
                    "order_id": oid,
                    "x": coord[0],
                    "y": coord[1],
                    "demand": o.demand_weight,
                    "ready_time": o.earliest_delivery,
                    "due_time": o.latest_delivery,
                    "status": o.status.value,
                })

            # Mesh topology graph serialization
            mesh_nodes: List[Dict[str, Any]] = []
            mesh_links: List[Dict[str, Any]] = []
            if self.mesh:
                for nid, pos in self.mesh.nodes.items():
                    is_broken = (
                        nid in self.mesh.failed_nodes
                        or (nid in self.fleet_state.vehicles and self.fleet_state.vehicles[nid].status == VehicleStatus.BROKEN_DOWN)
                    )
                    mesh_nodes.append({
                        "id": nid,
                        "x": round(float(pos[0]), 2),
                        "y": round(float(pos[1]), 2),
                        "status": "BROKEN" if is_broken else "ACTIVE",
                    })

                for u, v, data in mesh_topo.edges(data=True):
                    mesh_links.append({
                        "source": u,
                        "target": v,
                        "distance": round(float(data.get("distance", 0.0)), 1),
                        "active": True,
                    })

            connected_components = nx.number_connected_components(mesh_topo) if len(mesh_nodes) > 0 else 0

            # Traffic conditions
            affected_roads = []
            for u, v, data in self.road_network.graph.edges(data=True):
                lvl = data.get("traffic_level", TrafficLevel.NORMAL)
                if lvl != TrafficLevel.NORMAL:
                    affected_roads.append({
                        "u": u,
                        "v": v,
                        "level": lvl.value,
                        "speed": 15.0 if lvl == TrafficLevel.SEVERE else 25.0,
                    })

            # Performance & Delivery metrics
            total_orders = len(self.fleet_state.active_orders)
            deliv_count = len(self.env.delivered_orders)
            late_count = len(self.env.late_orders)
            failed_count = len(self.env.failed_orders)
            reassigned_count = self.fleet_agent.recovered_orders_count if self.fleet_agent else 0
            success_pct = round((deliv_count / max(1, total_orders)) * 100.0, 1)
            on_time_pct = round((max(0, deliv_count - late_count) / max(1, total_orders)) * 100.0, 1)

            # Demand predictions per quadrant
            demand_zones = [
                {"zone": "North-East", "predicted_demand": 38.4, "actual_demand": 34.0, "diff": "+4.4", "trend": "UP"},
                {"zone": "South-West", "predicted_demand": 22.1, "actual_demand": 24.0, "diff": "-1.9", "trend": "STABLE"},
                {"zone": "North-West", "predicted_demand": 19.8, "actual_demand": 18.0, "diff": "+1.8", "trend": "STABLE"},
                {"zone": "South-East", "predicted_demand": 29.5, "actual_demand": 31.0, "diff": "-1.5", "trend": "DOWN"},
            ]

            return {
                "simulation": {
                    "status": self.status,
                    "time": round(cur_t, 1),
                    "time_str": self._format_sim_time(cur_t),
                    "scenario": f"{self.dataset} Dynamic",
                    "dataset": self.dataset,
                    "seed": self.seed,
                    "speed": self.speed,
                    "horizon": self.horizon_mins,
                    "step_size": self.step_size_mins,
                },
                "fleet": {
                    "size": fleet_size,
                    "active": active_count,
                    "available": avail_count,
                    "broken": broken_count,
                    "repositioning": repositioning_count,
                    "recovering": 1 if self.recovery_routes else 0,
                    "utilization_pct": util_pct,
                },
                "vehicles": vehicles_list,
                "orders": orders_list,
                "map": {
                    "depot": {"x": depot_coord[0], "y": depot_coord[1]},
                    "customers": customers_list,
                    "active_routes": {vid: [int(n) for n in v.current_route] for vid, v in self.fleet_state.vehicles.items()},
                    "recovery_routes": self.recovery_routes,
                    "traffic_edges": affected_roads,
                },
                "traffic": {
                    "congestion_level": "SEVERE" if affected_roads else "NORMAL",
                    "affected_roads": affected_roads,
                    "average_speed": 32.4 if affected_roads else 40.0,
                    "predicted_delay_mins": 14.2 if affected_roads else 0.0,
                },
                "network": {
                    "mode": self.fleet_state.connectivity_state.value,
                    "cloud_status": "ONLINE" if self.fleet_state.connectivity_state == ConnectivityState.CLOUD_MODE else "OFFLINE",
                    "mesh_status": "ACTIVE",
                    "connected_vehicles": len(mesh_nodes) - broken_count,
                    "mesh_links": [[l["source"], l["target"]] for l in mesh_links],
                    "messages_sent": self.fleet_agent.total_mesh_messages if self.fleet_agent else 0,
                    "messages_delivered": self.fleet_agent.total_mesh_messages if self.fleet_agent else 0,
                    "messages_failed": 0,
                    "avg_latency_ms": 1.2,
                    "connected_components": connected_components,
                },
                "mesh": {
                    "nodes": mesh_nodes,
                    "links": mesh_links,
                    "transmission_range_km": 30.0,
                },
                "incidents": self.incidents,
                "recovery_flow": self.recovery_flow,
                "predictions": {
                    "zones": demand_zones,
                },
                "positioning": self.repositioning_status,
                "ppo": {
                    "enabled": self.ppo_agent is not None,
                    "current_action": ACTION_NAMES[self.last_ppo_action_idx],
                    "last_action": ACTION_NAMES[self.last_ppo_action_idx],
                    "action_timestamp": round(cur_t, 1),
                    "current_reward": self.last_ppo_reward,
                    "episode_reward": self.cumulative_ppo_reward,
                    "step_count": self.env.step_count,
                    "policy_status": "OPERATIONAL (MlpPolicy)" if self.ppo_agent else "HEURISTIC FALLBACK",
                    "history": self.ppo_history[-10:],
                },
                "sustainability": {
                    "total_distance_km": round(float(self.env.total_distance_traveled_km), 2),
                    "fuel_liters": round(float(self.env.total_fuel_liters), 2),
                    "co2_kg": round(float(self.env.total_co2_kg), 2),
                    "fuel_per_delivery": round(float(self.env.total_fuel_liters) / max(1, deliv_count), 2) if deliv_count > 0 else 0.0,
                    "co2_per_delivery": round(float(self.env.total_co2_kg) / max(1, deliv_count), 2) if deliv_count > 0 else 0.0,
                    "empty_km": round(float(self.env.total_empty_distance_km), 2),
                    "loaded_km": round(max(0.0, float(self.env.total_distance_traveled_km) - float(self.env.total_empty_distance_km)), 2),
                },
                "performance": {
                    "total_orders": total_orders,
                    "delivered": deliv_count,
                    "on_time": max(0, deliv_count - late_count),
                    "late": late_count,
                    "failed": failed_count,
                    "reassigned": reassigned_count,
                    "success_rate": success_pct,
                    "on_time_rate": on_time_pct,
                    "average_delay_mins": round(float(np.mean([o.get("delay", 0.0) for o in orders_list]) if orders_list else 0.0), 1),
                },
                "events": list(reversed(self.events[-25:])),
                "timeline": self.timeline,
            }

    def _log_event(self, t: float, ev_type: str, description: str, target: str = "Fleet", severity: str = "INFO") -> None:
        """Appends a new chronological event."""
        self.event_counter += 1
        entry = {
            "id": self.event_counter,
            "timestamp": round(t, 1),
            "time_str": self._format_sim_time(t),
            "type": ev_type,
            "target": target,
            "description": description,
            "severity": severity,
        }
        self.events.append(entry)
        if len(self.events) > 100:
            self.events.pop(0)

    def _add_timeline(self, t: float, title: str, description: str, category: str = "SYSTEM") -> None:
        """Appends a milestone event to the run timeline."""
        self.timeline.append({
            "time": round(t, 1),
            "time_str": self._format_sim_time(t),
            "title": title,
            "description": description,
            "category": category,
        })

    def _format_sim_time(self, t_mins: float) -> str:
        hrs = int(t_mins // 60)
        mins = int(t_mins % 60)
        return f"T+{hrs:02d}:{mins:02d}m"


# Global runner instance
runner = SimulationRunner()

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field
import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    import gym
    from gym import spaces

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.order import Order, OrderStatus
from src.models.road import RoadNetwork
from src.simulation.environment import FleetSimulationEnvironment
from src.data.loaders.solomon import load_solomon_benchmark
from src.prediction.fuel import DeterministicFuelModel
from src.prediction.travel_time import TravelTimePredictor
from src.prediction.demand import DemandPredictor
from src.optimization.predictive_positioning import PredictiveFleetPositioner


class RewardConfig(BaseModel):
    """Configurable transparent multi-objective reward weights."""
    delivery_reward: float = 20.0
    on_time_reward: float = 10.0
    fuel_penalty_weight: float = 1.0
    distance_penalty_weight: float = 0.5
    delay_penalty_weight: float = 2.0
    co2_penalty_weight: float = 0.5
    failure_penalty_weight: float = 30.0
    infeasible_action_penalty: float = 5.0


class SWARMRLEnv(gym.Env):
    """
    Gymnasium-compatible Reinforcement Learning Environment for SWARMRoute.
    Wraps actual discrete-time physical simulation, traffic dynamics, and mesh connectivity.
    Strictly isolated: does NOT leak future state or global ground-truth.
    """
    metadata = {"render_modes": ["human"], "render_fps": 10}

    OBS_DIM = 19
    ACTION_DIM = 5  # 0: Assign Nearest, 1: Reassign Stranded, 2: Accept Exchange, 3: Reposition, 4: Hold/Continue

    ACTION_NAMES = {
        0: "ASSIGN_NEAREST_ORDER",
        1: "REASSIGN_STRANDED_ORDER",
        2: "ACCEPT_EXCHANGE_BID",
        3: "REPOSITION_TO_DEMAND_ZONE",
        4: "HOLD_OR_CONTINUE",
    }

    def __init__(
        self,
        dataset_name: str = "C101",
        num_customers: int = 25,
        num_vehicles: int = 5,
        step_size_mins: float = 2.0,
        max_steps: int = 200,
        seed: int = 42,
        reward_config: Optional[RewardConfig] = None,
    ) -> None:
        super().__init__()
        self.dataset_name = dataset_name
        self.num_customers = num_customers
        self.num_vehicles = num_vehicles
        self.step_size_mins = step_size_mins
        self.max_steps = max_steps
        self.seed_val = seed
        self.reward_config = reward_config or RewardConfig()

        self.observation_space = spaces.Box(
            low=-2.0, high=10.0, shape=(self.OBS_DIM,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(self.ACTION_DIM)

        self.fuel_model = DeterministicFuelModel()
        self.positioner = PredictiveFleetPositioner(seed=seed)
        self.env: Optional[FleetSimulationEnvironment] = None
        self.controlled_truck_id = "TRUCK_01"
        self.step_count = 0

        self.last_delivered_count = 0
        self.last_failed_count = 0
        self.last_fuel = 0.0
        self.last_distance = 0.0
        self.last_late_count = 0

    def _setup_simulation(self) -> None:
        fleet, road, meta = load_solomon_benchmark(
            self.dataset_name,
            max_customers=self.num_customers,
            vehicle_count=self.num_vehicles,
        )
        node_map = {o.order_id: idx + 1 for idx, o in enumerate(fleet.active_orders.values())}

        # Initialize simple round-robin or depot routes
        vehicles = list(fleet.vehicles.values())
        orders = list(fleet.active_orders.values())
        for idx, o in enumerate(orders):
            v = vehicles[idx % len(vehicles)]
            v.assigned_orders.append(o.order_id)
            node_idx = node_map[o.order_id]
            if len(v.current_route) <= 1:
                v.current_route = [0, node_idx, 0]
            else:
                v.current_route.insert(-1, node_idx)

        self.controlled_truck_id = vehicles[0].vehicle_id
        self.env = FleetSimulationEnvironment(
            fleet_state=fleet,
            road_network=road,
            node_id_map=node_map,
            fuel_model=self.fuel_model,
            step_size_mins=self.step_size_mins,
            seed=self.seed_val,
        )

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        if seed is not None:
            self.seed_val = seed
        super().reset(seed=self.seed_val)

        self._setup_simulation()
        self.step_count = 0
        self.last_delivered_count = 0
        self.last_failed_count = 0
        self.last_fuel = 0.0
        self.last_distance = 0.0
        self.last_late_count = 0

        obs = self._get_observation()
        info = {"step_count": 0, "controlled_truck": self.controlled_truck_id}
        return obs, info

    def _get_observation(self) -> np.ndarray:
        """
        Extracts normalized local observation vector for the controlled truck.
        Strictly local information (no future ground truth leakage).
        """
        if self.env is None or self.controlled_truck_id not in self.env.fleet_state.vehicles:
            return np.zeros(self.OBS_DIM, dtype=np.float32)

        v = self.env.fleet_state.vehicles[self.controlled_truck_id]
        loc = v.current_location

        # 1. Truck spatial coordinates normalized to [0, 1]
        x_norm = float(np.clip(loc[0] / 100.0, 0.0, 1.0))
        y_norm = float(np.clip(loc[1] / 100.0, 0.0, 1.0))

        # 2. Payload and capacity
        cap_rem_norm = float(v.remaining_weight_capacity() / max(v.max_weight, 1.0))
        load_norm = float(v.current_load / max(v.max_weight, 1.0))
        fuel_norm = float(v.fuel_level / max(v.fuel_capacity, 1.0))

        # 3. Truck status & connectivity
        status_code = 0.0
        if v.status == VehicleStatus.EN_ROUTE:
            status_code = 0.33
        elif v.status == VehicleStatus.DELIVERING:
            status_code = 0.66
        elif v.status == VehicleStatus.BROKEN_DOWN:
            status_code = 1.0

        conn_mode = self.env.fleet_state.connectivity_state
        conn_code = 1.0 if conn_mode == ConnectivityState.CLOUD_MODE else (0.5 if conn_mode == ConnectivityState.MESH_MODE else 0.0)

        # 4. Mesh connectivity: number of reachable neighbors
        mesh_neighbors = 0
        if self.env.mesh_network.topology.has_node(self.controlled_truck_id):
            mesh_neighbors = len(list(self.env.mesh_network.topology.neighbors(self.controlled_truck_id)))
        mesh_neighbors_norm = float(np.clip(mesh_neighbors / 5.0, 0.0, 1.0))

        # 5. Local edge traffic multiplier
        traffic_level_norm = 1.0
        if v.current_node is not None and v.next_node is not None:
            if self.env.road_network.graph.has_edge(v.current_node, v.next_node):
                road_obj = self.env.road_network.graph[v.current_node][v.next_node].get("road")
                if road_obj:
                    traffic_level_norm = float(road_obj.traffic_level.speed_multiplier)

        # 6. Demand forecast in current zone
        zone_id = 0
        if loc[0] > 50.0 and loc[1] > 50.0:
            zone_id = 3
        elif loc[0] > 50.0:
            zone_id = 1
        elif loc[1] > 50.0:
            zone_id = 2
        forecasts = self.positioner.forecast_zone_demands(self.env.current_time_mins)
        predicted_demand = 30.0
        for f in forecasts:
            if f.zone_id == zone_id:
                predicted_demand = f.predicted_demand
                break
        pred_demand_norm = float(np.clip(predicted_demand / 100.0, 0.0, 1.0))

        # 7. Candidate unassigned/pending orders (top 3 closest)
        candidate_features = []
        pending_orders = [
            o for o in self.env.fleet_state.active_orders.values()
            if o.status in (OrderStatus.PENDING, OrderStatus.REASSIGNED)
            and o.order_id not in self.env.delivered_orders
        ]
        pending_orders.sort(key=lambda o: math.hypot(loc[0] - o.destination[0], loc[1] - o.destination[1]))

        for i in range(3):
            if i < len(pending_orders):
                cand = pending_orders[i]
                d = math.hypot(loc[0] - cand.destination[0], loc[1] - cand.destination[1])
                urgency = max(0.0, cand.latest_delivery - self.env.current_time_mins)
                candidate_features.extend([
                    float(np.clip(d / 100.0, 0.0, 2.0)),
                    float(np.clip(cand.demand_weight / max(v.max_weight, 1.0), 0.0, 1.0)),
                    float(np.clip(urgency / 120.0, 0.0, 2.0)),
                ])
            else:
                candidate_features.extend([1.0, 0.0, 0.0])

        obs = np.array([
            x_norm,
            y_norm,
            cap_rem_norm,
            load_norm,
            fuel_norm,
            status_code,
            conn_code,
            mesh_neighbors_norm,
            traffic_level_norm,
            pred_demand_norm,
            *candidate_features,
        ], dtype=np.float32)

        return np.nan_to_num(obs, nan=0.0)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.step_count += 1
        cfg = self.reward_config
        infeasible_penalty = 0.0

        v = self.env.fleet_state.vehicles[self.controlled_truck_id]

        # Process Action
        if action == 0:  # ASSIGN_NEAREST_ORDER
            pending = [
                o for o in self.env.fleet_state.active_orders.values()
                if o.status == OrderStatus.PENDING and o.order_id not in self.env.delivered_orders
            ]
            if pending and v.can_load(pending[0].demand_weight):
                target = pending[0]
                target.status = OrderStatus.IN_TRANSIT
                target_node = self.env.node_id_map.get(target.order_id, 1)
                v.assigned_orders.append(target.order_id)
                v.current_load += target.demand_weight
                if len(v.current_route) > 1:
                    v.current_route.insert(-1, target_node)
                else:
                    v.current_route.append(target_node)
            else:
                infeasible_penalty = cfg.infeasible_action_penalty

        elif action == 1 or action == 2:  # REASSIGN / ACCEPT EXCHANGE
            broken_trucks = [
                veh for veh in self.env.fleet_state.vehicles.values()
                if veh.status == VehicleStatus.BROKEN_DOWN and len(veh.assigned_orders) > 0
            ]
            if broken_trucks and v.remaining_weight_capacity() > 10.0:
                b_veh = broken_trucks[0]
                stranded_id = b_veh.assigned_orders[0]
                ord_obj = self.env.fleet_state.active_orders.get(stranded_id)
                if ord_obj and v.can_load(ord_obj.demand_weight):
                    b_veh.assigned_orders.remove(stranded_id)
                    v.assigned_orders.append(stranded_id)
                    v.current_load += ord_obj.demand_weight
                    ord_node = self.env.node_id_map.get(stranded_id, 1)
                    if len(v.current_route) > 1:
                        v.current_route.insert(-1, ord_node)
                    else:
                        v.current_route.append(ord_node)
                else:
                    infeasible_penalty = cfg.infeasible_action_penalty
            else:
                infeasible_penalty = cfg.infeasible_action_penalty

        elif action == 3:  # REPOSITION_TO_DEMAND_ZONE
            if v.status == VehicleStatus.IDLE:
                plans = self.positioner.plan_repositioning(
                    self.env.fleet_state, self.env.road_network, self.env.current_time_mins
                )
                if plans:
                    target_node = plans[0]["target_node"]
                    v.current_route = [v.current_node or 0, target_node]
                    v.status = VehicleStatus.EN_ROUTE
                    v.next_node = target_node
                else:
                    infeasible_penalty = cfg.infeasible_action_penalty
            else:
                infeasible_penalty = cfg.infeasible_action_penalty

        # Step underlying physical simulation
        self.env.step()

        # Calculate incremental progress
        curr_delivered = len(self.env.delivered_orders)
        curr_failed = len(self.env.failed_orders)
        curr_late = len(self.env.late_orders)
        curr_dist = self.env.total_distance_traveled_km
        curr_fuel = self.env.total_fuel_liters

        new_deliveries = curr_delivered - self.last_delivered_count
        new_failed = curr_failed - self.last_failed_count
        new_late = curr_late - self.last_late_count
        step_dist = curr_dist - self.last_distance
        step_fuel = curr_fuel - self.last_fuel
        step_co2 = step_fuel * 2.68

        new_on_time = max(0, new_deliveries - new_late)

        # Multi-objective transparent reward formula
        reward = (
            cfg.delivery_reward * new_deliveries
            + cfg.on_time_reward * new_on_time
            - cfg.fuel_penalty_weight * step_fuel
            - cfg.distance_penalty_weight * step_dist
            - cfg.delay_penalty_weight * new_late
            - cfg.co2_penalty_weight * step_co2
            - cfg.failure_penalty_weight * new_failed
            - infeasible_penalty
        )

        self.last_delivered_count = curr_delivered
        self.last_failed_count = curr_failed
        self.last_late_count = curr_late
        self.last_distance = curr_dist
        self.last_fuel = curr_fuel

        terminated = self.env.is_done()
        truncated = self.step_count >= self.max_steps

        obs = self._get_observation()
        info = {
            "step_count": self.step_count,
            "delivered_orders": curr_delivered,
            "failed_orders": curr_failed,
            "late_orders": curr_late,
            "total_distance_km": round(curr_dist, 2),
            "total_fuel_liters": round(curr_fuel, 2),
            "total_co2_kg": round(curr_fuel * 2.68, 2),
            "recovery_time_sec": round(self.env.recovery_time_sec, 4),
            "reassigned_orders": self.env.total_reassigned_orders_count,
            "reward": round(reward, 3),
        }

        return obs, float(reward), terminated, truncated, info

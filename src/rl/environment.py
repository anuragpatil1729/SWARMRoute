from __future__ import annotations
import math
from typing import Any, Dict, Optional, Tuple
import numpy as np

import gymnasium as gym
from gymnasium import spaces

from src.models.fleet_state import ConnectivityState
from src.models.vehicle import VehicleStatus
from src.models.order import Order, OrderStatus
from src.models.road import TrafficLevel
from src.simulation.environment import FleetSimulationEnvironment
from src.simulation.events import FleetEvent, EventType
from src.data.loaders.solomon import load_solomon_benchmark
from src.prediction.fuel import DeterministicFuelModel
from src.prediction.travel_time import TravelTimePredictor
from src.prediction.fuel_ml import FuelConsumptionPredictor
from src.prediction.demand import DemandPredictor
from src.optimization.predictive_positioning import PredictiveFleetPositioner
from src.networking.mesh import MeshNetwork
from src.agents.fleet_agent import FleetAgent
from src.rl.reward import MultiObjectiveRewardConfig, FleetRewardCalculator, RewardConfig
from src.data.weather import get_default_provider, WeatherProvider, WeatherSnapshot


__all__ = [
    "SWARMRLEnv",
    "RewardConfig",
    "MultiObjectiveRewardConfig",
    "FleetRewardCalculator",
    "ACTION_ASSIGN_BEST_ORDER",
    "ACTION_REASSIGN_STRANDED_ORDER",
    "ACTION_ACCEPT_OR_REJECT_TRANSFER",
    "ACTION_REPOSITION_TO_DEMAND_ZONE",
    "ACTION_HOLD_OR_CONTINUE",
]
# Action Constants
ACTION_ASSIGN_BEST_ORDER = 0
ACTION_REASSIGN_STRANDED_ORDER = 1
ACTION_ACCEPT_OR_REJECT_TRANSFER = 2
ACTION_REPOSITION_TO_DEMAND_ZONE = 3
ACTION_HOLD_OR_CONTINUE = 4


class SWARMRLEnv(gym.Env):
    """
    Gymnasium-compatible Reinforcement Learning Environment for SWARMRoute.
    Directly controls real multi-vehicle fleet decision making over discrete simulation ticks.
    Enforces a strict local information barrier: zero global ground-truth or future disruption leakage.
    """
    metadata = {"render_modes": ["human"], "render_fps": 10}

    OBS_DIM = 25
    ACTION_DIM = 5  # 0: Assign Best, 1: Reassign Stranded, 2: Accept/Reject Transfer, 3: Reposition, 4: Hold/Continue

    ACTION_NAMES = {
        0: "ASSIGN_BEST_ORDER",
        1: "REASSIGN_STRANDED_ORDER",
        2: "ACCEPT_OR_REJECT_TRANSFER",
        3: "REPOSITION_TO_DEMAND_ZONE",
        4: "HOLD_OR_CONTINUE",
    }

    def __init__(
        self,
        dataset_name: str = "C101",
        num_customers: int = 25,
        num_vehicles: int = 5,
        step_size_mins: float = 2.0,
        max_steps: int = 300,
        seed: int = 42,
        reward_config: Optional[MultiObjectiveRewardConfig] = None,
        travel_time_predictor: Optional[TravelTimePredictor] = None,
        fuel_predictor: Optional[FuelConsumptionPredictor] = None,
        demand_predictor: Optional[DemandPredictor] = None,
        weather_provider: Optional[WeatherProvider] = None,
    ) -> None:
        super().__init__()
        self.dataset_name = dataset_name
        self.num_customers = num_customers
        self.num_vehicles = num_vehicles
        self.step_size_mins = step_size_mins
        self.max_steps = max_steps
        self.seed_val = seed
        self.reward_calculator = FleetRewardCalculator(reward_config)
        self.travel_time_predictor = travel_time_predictor
        self.fuel_predictor = fuel_predictor
        self.demand_predictor = demand_predictor
        self.weather_provider = weather_provider or get_default_provider(use_live=False, seed=seed)


        self.observation_space = spaces.Box(
            low=-5.0, high=10.0, shape=(self.OBS_DIM,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(self.ACTION_DIM)

        self.fuel_model = DeterministicFuelModel()
        self.positioner = PredictiveFleetPositioner(demand_predictor=demand_predictor, seed=seed)
        self.env: Optional[FleetSimulationEnvironment] = None
        self.fleet_agent: Optional[FleetAgent] = None
        self.controlled_truck_id = "TRUCK_01"
        self.step_count = 0

        # Incremental tracking counters for reward computation
        self.last_delivered_count = 0
        self.last_late_count = 0
        self.last_failed_count = 0
        self.last_recovered_count = 0
        self.last_fuel = 0.0
        self.last_distance = 0.0
        self.last_empty_km = 0.0

    def _setup_simulation(self) -> None:
        fleet, road, meta = load_solomon_benchmark(
            self.dataset_name,
            max_customers=self.num_customers,
            vehicle_count=self.num_vehicles,
        )
        node_map = {o.order_id: idx + 1 for idx, o in enumerate(fleet.active_orders.values())}

        # Initialize baseline initial routes
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
            v.status = VehicleStatus.EN_ROUTE

        self.controlled_truck_id = vehicles[0].vehicle_id
        mesh = MeshNetwork(transmission_range_km=30.0, seed=self.seed_val)
        self.env = FleetSimulationEnvironment(
            fleet_state=fleet,
            road_network=road,
            node_id_map=node_map,
            fuel_model=self.fuel_model,
            mesh_network=mesh,
            weather_provider=self.weather_provider,
            step_size_mins=self.step_size_mins,
            seed=self.seed_val,
        )
        # The policy's recovery action uses the same mesh contract-net path as
        # the operational simulator; it is not a parallel rule-only shortcut.
        self.fleet_agent = FleetAgent(
            fleet_state=fleet,
            road_network=road,
            mesh_network=mesh,
            fuel_predictor=self.fuel_predictor,
            use_ml_fuel=bool(self.fuel_predictor and getattr(self.fuel_predictor, "is_trained", False)),
            seed=self.seed_val,
        )


        # Schedule training disruption scenario
        if len(vehicles) > 1:
            self.env.event_engine.schedule(
                FleetEvent(
                    event_id="EV_TRAIN_BREAKDOWN",
                    event_type=EventType.VEHICLE_BREAKDOWN,
                    timestamp=30.0,
                    payload={"vehicle_id": vehicles[0].vehicle_id},
                )
            )
            self.env.event_engine.schedule(
                FleetEvent(
                    event_id="EV_TRAIN_CONN_LOSS",
                    event_type=EventType.CONNECTIVITY_LOSS,
                    timestamp=30.0,
                    payload={},
                )
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
        self.last_late_count = 0
        self.last_failed_count = 0
        self.last_recovered_count = 0
        self.last_fuel = 0.0
        self.last_distance = 0.0
        self.last_empty_km = 0.0
        self.last_delay_mins = 0.0

        obs = self._get_observation()
        info = {
            "step_count": 0,
            "controlled_truck": self.controlled_truck_id,
            "controlled_truck_id": self.controlled_truck_id,
        }
        return obs, info

    def _get_observation(self) -> np.ndarray:
        """
        Builds a 25-dimensional normalized local observation vector.
        Contains dynamic local features with zero global oracle or unrevealed disruption leakage.
        """
        if self.env is None or not self.env.fleet_state.vehicles:
            return np.zeros(self.OBS_DIM, dtype=np.float32)

        # Select an active truck if controlled truck is broken
        ctrl_id = self.controlled_truck_id
        if ctrl_id not in self.env.fleet_state.vehicles or self.env.fleet_state.vehicles[ctrl_id].status == VehicleStatus.BROKEN_DOWN:
            active_trucks = [
                vid for vid, veh in self.env.fleet_state.vehicles.items()
                if veh.status != VehicleStatus.BROKEN_DOWN
            ]
            if active_trucks:
                ctrl_id = active_trucks[0]
                self.controlled_truck_id = ctrl_id

        v = self.env.fleet_state.vehicles.get(ctrl_id)
        if v is None:
            return np.zeros(self.OBS_DIM, dtype=np.float32)

        loc = v.current_location or (0.0, 0.0)
        t_norm = float(np.clip(self.env.current_time_mins / 1200.0, 0.0, 2.0))
        x_norm = float(np.clip(loc[0] / 100.0, 0.0, 1.0))
        y_norm = float(np.clip(loc[1] / 100.0, 0.0, 1.0))
        cap_rem_norm = float(np.clip(v.remaining_weight_capacity() / max(v.max_weight, 1.0), 0.0, 1.0))
        load_norm = float(np.clip(v.current_load / max(v.max_weight, 1.0), 0.0, 1.0))
        fuel_norm = float(np.clip(v.fuel_level / 100.0, 0.0, 1.0))

        # Environmental friction index (traffic congestion and adverse weather severity)
        traffic_norm = 0.2
        if v.current_node is not None and v.next_node is not None:
            if self.env.road_network.graph.has_edge(v.current_node, v.next_node):
                t_level = self.env.road_network.graph.edges[v.current_node, v.next_node].get("traffic_level", TrafficLevel.NORMAL)
                traffic_norm = 1.0 if t_level in (TrafficLevel.SEVERE, TrafficLevel.BLOCKED) else (0.6 if t_level == TrafficLevel.HEAVY else 0.2)

        if self.weather_provider is not None:
            weather_snap = self.weather_provider.get_current(loc[0], loc[1])
            weather_severity = weather_snap.severity
            traffic_norm = float(np.clip(max(traffic_norm, weather_severity), 0.0, 1.0))


        # Stranded orders count (orders assigned to broken trucks that are not delivered)
        stranded_count = sum(
            len([oid for oid in veh.assigned_orders if oid not in self.env.delivered_orders])
            for veh in self.env.fleet_state.vehicles.values()
            if veh.status == VehicleStatus.BROKEN_DOWN
        )
        stranded_norm = float(np.clip(stranded_count / max(1, len(self.env.fleet_state.active_orders)), 0.0, 1.0))

        # Fleet availability and breakdowns
        total_vehs = len(self.env.fleet_state.vehicles)
        broken_vehs = sum(1 for veh in self.env.fleet_state.vehicles.values() if veh.status == VehicleStatus.BROKEN_DOWN)
        avail_vehs = total_vehs - broken_vehs
        avail_norm = float(np.clip(avail_vehs / max(1, total_vehs), 0.0, 1.0))
        broken_norm = float(np.clip(broken_vehs / max(1, total_vehs), 0.0, 1.0))

        # Mesh connectivity and neighbors
        mesh_neighbors = 0
        if self.env.mesh_network.topology.has_node(ctrl_id):
            mesh_neighbors = len(list(self.env.mesh_network.topology.neighbors(ctrl_id)))
        else:
            mesh_neighbors = sum(
                1 for n_id, pos in self.env.mesh_network.nodes.items()
                if n_id != ctrl_id and math.hypot(pos[0] - loc[0], pos[1] - loc[1]) <= self.env.mesh_network.transmission_range_km
            )
        mesh_neighbors_norm = float(np.clip(mesh_neighbors / max(1, total_vehs), 0.0, 1.0))
        conn_code = 1.0 if self.env.fleet_state.connectivity_state == ConnectivityState.CLOUD_MODE else (
            0.5 if self.env.fleet_state.connectivity_state == ConnectivityState.MESH_MODE else 0.0
        )

        # Predicted demand in current quadrant
        zone_id = 0
        if loc[0] > 50.0 and loc[1] > 50.0:
            zone_id = 3
        elif loc[0] > 50.0:
            zone_id = 1
        elif loc[1] > 50.0:
            zone_id = 2
        forecasts = self.positioner.forecast_zone_demands(
            self.env.current_time_mins,
            orders=list(self.env.fleet_state.active_orders.values()),
        )
        pred_demand = next((f.predicted_demand for f in forecasts if f.zone_id == zone_id), 0.0)
        pred_demand_norm = float(np.clip(pred_demand / 100.0, 0.0, 1.0))

        # Route info
        route_len = max(1, len(v.current_route))
        route_idx = getattr(v, "route_index", 0)
        route_prog_norm = float(np.clip(route_idx / route_len, 0.0, 1.0))
        rem_stops_norm = float(np.clip(max(0, route_len - route_idx) / 15.0, 0.0, 2.0))

        # Delivery urgency
        assigned_objs = [self.env.fleet_state.active_orders[oid] for oid in v.assigned_orders if oid in self.env.fleet_state.active_orders]
        earliest_due = min([o.latest_delivery for o in assigned_objs], default=self.env.current_time_mins + 100.0)
        urgency_norm = float(np.clip((earliest_due - self.env.current_time_mins) / 120.0, -1.0, 2.0))

        # Top-3 candidate orders (pending or stranded)
        cand_features = []
        stranded_ids = {
            oid
            for veh in self.env.fleet_state.vehicles.values()
            if veh.status == VehicleStatus.BROKEN_DOWN
            for oid in veh.assigned_orders
            if oid not in self.env.delivered_orders
        }
        cands = [
            o for o in self.env.fleet_state.active_orders.values()
            if (o.status in (OrderStatus.PENDING, OrderStatus.REASSIGNED) or o.order_id in stranded_ids)
            and o.order_id not in self.env.delivered_orders
        ]
        cands.sort(key=lambda o: math.hypot(loc[0] - o.destination[0], loc[1] - o.destination[1]))

        for i in range(3):
            if i < len(cands):
                cand = cands[i]
                d = math.hypot(loc[0] - cand.destination[0], loc[1] - cand.destination[1])

                # ML-informed effective distance: blend raw geometric distance with
                # predicted travel time and predicted fuel cost when trained models
                # are available, so the policy actually observes what the predictors know.
                eff_d = d
                if self.travel_time_predictor and getattr(self.travel_time_predictor, "is_trained", False):
                    try:
                        pred_hrs = self.travel_time_predictor.predict_trip(
                            distance_km=d,
                            traffic_level=TrafficLevel.NORMAL.value,
                            hour_of_day=int((self.env.current_time_mins / 60.0) % 24),
                            is_weekend=False,
                        )
                        # convert predicted minutes back into a distance-equivalent
                        # using the vehicle's nominal speed, so units stay comparable
                        eff_d = (pred_hrs * 60.0 / 60.0) * max(1.0, v.average_speed)
                    except Exception:
                        pass

                fuel_ratio = (v.fuel_efficiency / 100.0) * d
                if self.fuel_predictor and getattr(self.fuel_predictor, "is_trained", False):
                    try:
                        fuel_ratio = self.fuel_predictor.predict_fuel(
                            distance_km=d,
                            vehicle_load_kg=v.current_load + cand.demand_weight,
                            max_payload_kg=v.max_weight,
                            average_speed_kmh=v.average_speed,
                        )
                    except Exception:
                        pass
                # fold fuel signal in as a small multiplicative penalty on effective distance
                eff_d = eff_d * (1.0 + np.clip(fuel_ratio / 50.0, 0.0, 0.5))

                cand_urgency = cand.latest_delivery - self.env.current_time_mins
                cand_features.extend([
                    float(np.clip(eff_d / 100.0, 0.0, 2.0)),
                    float(np.clip(cand.demand_weight / max(v.max_weight, 1.0), 0.0, 1.0)),
                    float(np.clip(cand_urgency / 120.0, -1.0, 2.0)),
                ])
            else:
                cand_features.extend([1.0, 0.0, 1.0])

        obs = np.array([
            t_norm,
            x_norm,
            y_norm,
            cap_rem_norm,
            load_norm,
            fuel_norm,
            traffic_norm,
            stranded_norm,
            avail_norm,
            broken_norm,
            mesh_neighbors_norm,
            conn_code,
            pred_demand_norm,
            route_prog_norm,
            rem_stops_norm,
            urgency_norm,
            *cand_features,
        ], dtype=np.float32)

        return np.nan_to_num(obs, nan=0.0, posinf=1.0, neginf=-1.0)

    def action_masks(self) -> np.ndarray:
        """
        Returns a boolean mask of shape (5,) indicating which discrete actions
        are structurally feasible in the current environment state.
        
        - Action 0 (ASSIGN_BEST_ORDER): Feasible if controlled truck is active and
          has capacity to load at least one pending order.
        - Action 1 (REASSIGN_STRANDED_ORDER): Feasible if broken_trucks[0] has an
          un-delivered order and at least one surviving truck can load it (mirrors step()).
        - Action 2 (ACCEPT_OR_REJECT_TRANSFER): Always feasible (evaluating or cleanly rejecting).
        - Action 3 (REPOSITION_TO_DEMAND_ZONE): Feasible if truck is IDLE and a repositioning
          target plan exists.
        - Action 4 (HOLD_OR_CONTINUE): Always feasible.
        """
        if self.env is None or not self.env.fleet_state.vehicles:
            return np.array([False, False, False, False, True], dtype=bool)

        ctrl_id = self.controlled_truck_id
        if ctrl_id not in self.env.fleet_state.vehicles or self.env.fleet_state.vehicles[ctrl_id].status == VehicleStatus.BROKEN_DOWN:
            active_trucks = [
                vid for vid, veh in self.env.fleet_state.vehicles.items()
                if veh.status != VehicleStatus.BROKEN_DOWN
            ]
            if active_trucks:
                ctrl_id = active_trucks[0]

        v = self.env.fleet_state.vehicles.get(ctrl_id)

        # Action 0: ASSIGN_BEST_ORDER
        mask_0 = False
        if v and v.status != VehicleStatus.BROKEN_DOWN:
            pending_orders = [
                o for o in self.env.fleet_state.active_orders.values()
                if o.status == OrderStatus.PENDING and o.order_id not in self.env.delivered_orders
            ]
            mask_0 = any(v.can_load(cand.demand_weight) for cand in pending_orders)

        # Action 1: REASSIGN_STRANDED_ORDER (exact mirror of step())
        mask_1 = False
        broken_trucks = [
            veh for veh in self.env.fleet_state.vehicles.values()
            if veh.status == VehicleStatus.BROKEN_DOWN and len(veh.assigned_orders) > 0
        ]
        if broken_trucks:
            target_broken = broken_trucks[0]
            stranded_id = target_broken.assigned_orders[0]
            ord_obj = self.env.fleet_state.active_orders.get(stranded_id)
            if ord_obj:
                mask_1 = any(
                    truck.status != VehicleStatus.BROKEN_DOWN and truck.can_load(ord_obj.demand_weight)
                    for truck in self.env.fleet_state.vehicles.values()
                )

        # Action 2: ACCEPT_OR_REJECT_TRANSFER (always valid)
        mask_2 = True

        # Action 3: REPOSITION_TO_DEMAND_ZONE
        # NOTE: At large scale (250k-1M steps), cache plan_repositioning result per tick
        mask_3 = False
        if v and v.status == VehicleStatus.IDLE:
            plans = self.positioner.plan_repositioning(
                self.env.fleet_state, self.env.road_network, self.env.current_time_mins
            )
            mask_3 = bool(plans)

        # Action 4: HOLD_OR_CONTINUE
        mask_4 = True

        return np.array([mask_0, mask_1, mask_2, mask_3, mask_4], dtype=bool)

    def get_action_mask(self) -> np.ndarray:
        """Alias for action_masks."""
        return self.action_masks()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.step_count += 1
        infeasible_action = False
        useful_repositioning = False
        excessive_reassignment = False
        recoveries_this_step = 0

        v = self.env.fleet_state.vehicles.get(self.controlled_truck_id)
        if v is None or v.status == VehicleStatus.BROKEN_DOWN:
            # Re-target an active truck
            active_trucks = [
                vid for vid, veh in self.env.fleet_state.vehicles.items()
                if veh.status != VehicleStatus.BROKEN_DOWN
            ]
            if active_trucks:
                self.controlled_truck_id = active_trucks[0]
                v = self.env.fleet_state.vehicles[self.controlled_truck_id]

        # ---------------------------------------------------------------------
        # ACTION 0: ASSIGN_BEST_ORDER
        # ---------------------------------------------------------------------
        if action == 0:
            pending_orders = [
                o for o in self.env.fleet_state.active_orders.values()
                if o.status == OrderStatus.PENDING and o.order_id not in self.env.delivered_orders
            ]
            assigned_order = None
            if v and pending_orders:
                # Rank orders using ML-predicted travel times, arrival feasibility, and fuel
                def score_order(cand: Order) -> Tuple[float, float, float]:
                    dist = math.hypot(v.current_location[0] - cand.destination[0], v.current_location[1] - cand.destination[1])
                    pred_mins = (dist / max(1.0, v.average_speed)) * 60.0
                    if self.travel_time_predictor and getattr(self.travel_time_predictor, "is_trained", False):
                        try:
                            pred_hrs = self.travel_time_predictor.predict_trip(
                                distance_km=dist,
                                traffic_level=TrafficLevel.NORMAL.value,
                                hour_of_day=int((self.env.current_time_mins / 60.0) % 24),
                                is_weekend=False,
                            )
                            pred_mins = pred_hrs * 60.0
                        except Exception:
                            pass
                    eta = self.env.current_time_mins + pred_mins
                    lateness_risk = max(0.0, eta - cand.latest_delivery)

                    pred_f = (v.fuel_efficiency / 100.0) * dist
                    if self.fuel_predictor and getattr(self.fuel_predictor, "is_trained", False):
                        try:
                            pred_f = self.fuel_predictor.predict_fuel(
                                distance_km=dist,
                                vehicle_load_kg=v.current_load + cand.demand_weight,
                                max_payload_kg=v.max_weight,
                                average_speed_kmh=v.average_speed,
                            )
                        except Exception:
                            pass
                    return (lateness_risk, pred_f, dist)

                pending_orders.sort(key=score_order)
                for cand in pending_orders:
                    if v.can_load(cand.demand_weight):
                        assigned_order = cand
                        break

            if assigned_order and v:
                assigned_order.status = OrderStatus.IN_TRANSIT
                target_node = self.env.node_id_map.get(assigned_order.order_id, 1)
                v.assigned_orders.append(assigned_order.order_id)
                v.current_load += assigned_order.demand_weight
                if len(v.current_route) > 1:
                    v.current_route.insert(-1, target_node)
                else:
                    v.current_route.append(target_node)
                if v.status == VehicleStatus.IDLE:
                    v.status = VehicleStatus.EN_ROUTE
            else:
                infeasible_action = True

        # ---------------------------------------------------------------------
        # ACTION 1: REASSIGN_STRANDED_ORDER (Breakdown Recovery)
        # ---------------------------------------------------------------------
        elif action == 1:
            broken_trucks = [
                veh for veh in self.env.fleet_state.vehicles.values()
                if veh.status == VehicleStatus.BROKEN_DOWN and len(veh.assigned_orders) > 0
            ]
            if broken_trucks:
                # Identify stranded orders
                target_broken = broken_trucks[0]
                stranded_id = target_broken.assigned_orders[0]
                ord_obj = self.env.fleet_state.active_orders.get(stranded_id)

                if self.fleet_agent is None:
                    infeasible_action = True
                else:
                    result = self.fleet_agent.on_vehicle_breakdown_decentralized(
                        target_broken.vehicle_id,
                        self.env.current_time_mins,
                        self.env.node_id_map,
                    )
                    recoveries_this_step = int(result.get("recovered_count", 0))
                    if recoveries_this_step:
                        self.env.total_reassigned_orders_count += recoveries_this_step
                    else:
                        infeasible_action = True
            else:
                infeasible_action = True

        # ---------------------------------------------------------------------
        # ACTION 2: ACCEPT_OR_REJECT_TRANSFER
        # ---------------------------------------------------------------------
        elif action == 2:
            # Evaluate peer exchange benefit
            reassigned = [
                o for o in self.env.fleet_state.active_orders.values()
                if o.status == OrderStatus.REASSIGNED and o.order_id not in self.env.delivered_orders
            ]
            if reassigned and v and v.remaining_weight_capacity() > 15.0:
                # Accept and integrate into local plan
                target = reassigned[0]
                target_node = self.env.node_id_map.get(target.order_id, 1)
                if target.order_id not in v.assigned_orders:
                    v.assigned_orders.append(target.order_id)
                    v.current_load += target.demand_weight
                    if len(v.current_route) > 1:
                        v.current_route.insert(-1, target_node)
                    else:
                        v.current_route.append(target_node)
            else:
                # Reject transfer cleanly (prevents overloading)
                pass

        # ---------------------------------------------------------------------
        # ACTION 3: REPOSITION_TO_DEMAND_ZONE
        # ---------------------------------------------------------------------
        elif action == 3:
            if v and v.status == VehicleStatus.IDLE:
                plans = self.positioner.plan_repositioning(
                    self.env.fleet_state, self.env.road_network, self.env.current_time_mins
                )
                if plans:
                    target_node = plans[0]["target_node"]
                    v.current_route = [v.current_node or 0, target_node]
                    v.status = VehicleStatus.EN_ROUTE
                    v.next_node = target_node
                    useful_repositioning = True
                else:
                    infeasible_action = True
            else:
                infeasible_action = True

        # ---------------------------------------------------------------------
        # ACTION 4: HOLD_OR_CONTINUE
        # ---------------------------------------------------------------------
        elif action == 4:
            # Maintain current schedule; no intervention
            pass

        # Step underlying physical simulator
        self.env.step()

        # Measure empirical deltas
        curr_delivered = len(self.env.delivered_orders)
        curr_late = len(self.env.late_orders)
        curr_failed = len(self.env.failed_orders)
        curr_dist = self.env.total_distance_traveled_km
        curr_fuel = self.env.total_fuel_liters
        curr_empty = self.env.total_empty_distance_km

        new_deliveries = curr_delivered - self.last_delivered_count
        new_late = curr_late - self.last_late_count
        new_failed = curr_failed - self.last_failed_count
        new_on_time = max(0, new_deliveries - new_late)

        delta_dist = max(0.0, curr_dist - self.last_distance)
        delta_fuel = max(0.0, curr_fuel - self.last_fuel)
        delta_co2 = delta_fuel * 2.68
        delta_empty = max(0.0, curr_empty - self.last_empty_km)

        # Incremental lateness minutes
        curr_delay_mins = sum(
            max(0.0, (self.env.fleet_state.active_orders[oid].actual_arrival_time or self.env.current_time_mins) - self.env.fleet_state.active_orders[oid].latest_delivery)
            for oid in self.env.late_orders
            if oid in self.env.fleet_state.active_orders
        )
        delta_delay = max(0.0, curr_delay_mins - getattr(self, "last_delay_mins", 0.0))
        self.last_delay_mins = curr_delay_mins

        fleet_util = 0.0
        active_vehs = [veh for veh in self.env.fleet_state.vehicles.values() if veh.status != VehicleStatus.BROKEN_DOWN]
        if active_vehs:
            fleet_util = sum(veh.utilization_rate for veh in active_vehs) / len(active_vehs)

        reward, decomp = self.reward_calculator.calculate_step_reward_decomposed(
            new_deliveries=new_deliveries,
            new_on_time=new_on_time,
            new_recoveries=recoveries_this_step,
            new_failed=new_failed,
            new_late=new_late,
            delay_minutes=delta_delay,
            incremental_distance_km=delta_dist,
            incremental_fuel_liters=delta_fuel,
            incremental_co2_kg=delta_co2,
            incremental_empty_km=delta_empty,
            fleet_utilization_ratio=fleet_util,
            useful_repositioning=useful_repositioning,
            infeasible_action=infeasible_action,
            excessive_reassignment=excessive_reassignment,
        )

        self.last_delivered_count = curr_delivered
        self.last_late_count = curr_late
        self.last_failed_count = curr_failed
        self.last_distance = curr_dist
        self.last_fuel = curr_fuel
        self.last_empty_km = curr_empty

        terminated = self.env.is_done()
        truncated = self.step_count >= self.max_steps

        obs = self._get_observation()
        info = {
            "step_count": self.step_count,
            "action_taken": self.ACTION_NAMES.get(action, "UNKNOWN"),
            "delivered_orders": curr_delivered,
            "late_orders": curr_late,
            "failed_orders": curr_failed,
            "recoveries_count": self.env.total_reassigned_orders_count,
            "total_distance_km": round(curr_dist, 2),
            "total_fuel_liters": round(curr_fuel, 2),
            "total_co2_kg": round(curr_fuel * 2.68, 2),
            "reward": reward,
            "reward_decomposition": decomp,
        }

        return obs, reward, terminated, truncated, info

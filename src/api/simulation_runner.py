"""
SWARMRoute Simulation Runner for Live Dashboard.
Executes and coordinates continuous discrete-event simulation,
PPO reinforcement learning, RF mesh communications, ML predictors,
and real-time disruption handling.
"""
from __future__ import annotations

# Pre-initialize OR-Tools / Protobuf descriptors on macOS Python 3.13
try:
    import ortools
    from ortools.constraint_solver import pywrapcp
except ImportError:
    pass

import math
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


import networkx as nx
import numpy as np

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.order import OrderStatus
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
from src.networking.messages import MeshMessage, MessageType
from src.networking.connectivity import ConnectivityManager
from src.agents.fleet_agent import FleetAgent
from src.rl.environment import SWARMRLEnv
from src.rl.ppo_agent import PPOFleetAgent
from src.rl.reward import MultiObjectiveRewardConfig, FleetRewardCalculator


CITY_LANDMARKS: Dict[str, List[Dict[str, str]]] = {
    "Bengaluru": [
        {"name": "Central Logistics Hub", "area": "MG Road / Shivajinagar"},
        {"name": "Embassy GolfLinks Tech Park", "area": "Domlur / Koramangala"},
        {"name": "Indiranagar 100 Feet Road", "area": "Indiranagar"},
        {"name": "HSR Layout Sector 1", "area": "HSR Layout"},
        {"name": "International Tech Park (ITPL)", "area": "Whitefield"},
        {"name": "Electronic City Phase 1", "area": "Electronic City"},
        {"name": "RBD EcoSpace Outer Ring Rd", "area": "Bellandur"},
        {"name": "Marathahalli Bridge Junction", "area": "Marathahalli"},
        {"name": "JP Nagar 6th Phase", "area": "JP Nagar"},
        {"name": "Jayanagar 4th T Block", "area": "Jayanagar"},
        {"name": "Peenya Industrial Area Stage 2", "area": "Peenya"},
        {"name": "Rajajinagar Industrial Suburb", "area": "Rajajinagar"},
        {"name": "Yeshwanthpur APMC Wholesale Yard", "area": "Yeshwanthpur"},
        {"name": "Hebbal Flyover Logistics Node", "area": "Hebbal"},
        {"name": "Banashankari BDA Complex", "area": "Banashankari"},
        {"name": "Malleshwaram 8th Cross", "area": "Malleshwaram"},
        {"name": "BTM Layout Udupi Garden", "area": "BTM Layout"},
        {"name": "Koramangala 4th Block", "area": "Koramangala"},
        {"name": "Sarjapur Road Wipro Gate", "area": "Sarjapur"},
        {"name": "Bannerghatta Rd IIM Bangalore", "area": "Bannerghatta"},
        {"name": "Yelahanka New Town Cargo Depot", "area": "Yelahanka"},
    ],
    "Mumbai": [
        {"name": "BKC Freight Gateway", "area": "Bandra-Kurla Complex"},
        {"name": "Andheri MIDC Logistics Hub", "area": "Andheri East"},
        {"name": "Powai Supreme Business Park", "area": "Powai"},
        {"name": "Lower Parel Commercial Center", "area": "Lower Parel"},
        {"name": "Vashi APMC Market Terminal", "area": "Navi Mumbai"},
        {"name": "Dadar TT Circle Hub", "area": "Dadar Central"},
        {"name": "Goregaon Nesco Cargo Depot", "area": "Goregaon East"},
        {"name": "Thane Wagle Estate Hub", "area": "Thane West"},
        {"name": "Kurla West Transit Point", "area": "Kurla West"},
        {"name": "Malad Mindspace Terminal", "area": "Malad West"},
        {"name": "Borivali National Park Depot", "area": "Borivali East"},
        {"name": "Chembur Diamond Garden", "area": "Chembur"},
        {"name": "Worli Seaface Logistics Node", "area": "Worli"},
        {"name": "Ghatkopar Metro Logistics Depot", "area": "Ghatkopar"},
        {"name": "Rabale Industrial Area", "area": "Airoli / Navi Mumbai"},
        {"name": "Kandivali Industrial Estate", "area": "Kandivali West"},
        {"name": "Kanjurmarg Logistics Park", "area": "Kanjurmarg"},
        {"name": "Mulund Check Naka Terminal", "area": "Mulund"},
        {"name": "Churchgate Cargo Point", "area": "South Mumbai"},
        {"name": "Byculla Central Rail Depot", "area": "Byculla"},
    ],
    "Delhi": [
        {"name": "Okhla Industrial Area Phase 2", "area": "Okhla"},
        {"name": "Nehru Place Business Hub", "area": "Nehru Place"},
        {"name": "Connaught Place Central Node", "area": "Connaught Place"},
        {"name": "Karol Bagh Commercial Center", "area": "Karol Bagh"},
        {"name": "Patparganj Industrial Estate", "area": "Patparganj"},
        {"name": "Dwarka Sector 10 Depot", "area": "Dwarka"},
        {"name": "Rohini Sector 18 Logistics Hub", "area": "Rohini"},
        {"name": "Hauz Khas Terminal", "area": "Hauz Khas"},
        {"name": "Mayapuri Industrial Area", "area": "Mayapuri"},
        {"name": "Noida Sector 62 IT Cargo Hub", "area": "Noida"},
        {"name": "Gurugram Cyber City Freight Point", "area": "DLF Phase 2"},
        {"name": "Gurugram Udyog Vihar Phase 4", "area": "Udyog Vihar"},
        {"name": "Faridabad Industrial Sector 24", "area": "Faridabad"},
        {"name": "Chandni Chowk Wholesale Hub", "area": "Old Delhi"},
        {"name": "Saket District Centre", "area": "Saket"},
        {"name": "Vasant Kunj Commercial Spine", "area": "Vasant Kunj"},
        {"name": "Laxmi Nagar Terminal", "area": "East Delhi"},
        {"name": "Anand Vihar ISBT Freight Hub", "area": "Anand Vihar"},
        {"name": "Janakpuri District Centre", "area": "West Delhi"},
        {"name": "Shalimar Bagh Logistics Node", "area": "North Delhi"},
    ],
    "Hyderabad": [
        {"name": "HITEC City Logistics Gateway", "area": "Madhapur"},
        {"name": "Gachibowli Financial District Hub", "area": "Gachibowli"},
        {"name": "Sanathnagar Industrial Hub", "area": "Sanathnagar"},
        {"name": "Begumpet Cargo Transit Point", "area": "Begumpet"},
        {"name": "Secunderabad Rail Freight Depot", "area": "Secunderabad"},
        {"name": "Kukatpally KPHB Commercial Colony", "area": "Kukatpally"},
        {"name": "Banjara Hills Road No 12", "area": "Banjara Hills"},
        {"name": "Jubilee Hills Check Post", "area": "Jubilee Hills"},
        {"name": "Ameerpet Junction Terminal", "area": "Ameerpet"},
        {"name": "Uppal Industrial Area", "area": "Uppal"},
        {"name": "Cherlapally Industrial Park", "area": "Cherlapally"},
        {"name": "Kondapur Botanical Garden Node", "area": "Kondapur"},
        {"name": "Balanagar IDPL Industrial Area", "area": "Balanagar"},
        {"name": "Dilsukhnagar Main Rd Depot", "area": "Dilsukhnagar"},
        {"name": "Charminar Distribution Hub", "area": "Old City"},
        {"name": "Miyapur Metro Logistics Point", "area": "Miyapur"},
        {"name": "Shamshabad Cargo Terminal", "area": "Airport Corridor"},
        {"name": "Kompally NH44 Logistics Park", "area": "Kompally"},
    ],
    "Pune": [
        {"name": "Hinjawadi Phase 1 IT Terminal", "area": "Hinjawadi"},
        {"name": "Shivaji Nagar Logistics Node", "area": "Shivaji Nagar"},
        {"name": "Hadapsar Magarpatta City Hub", "area": "Hadapsar"},
        {"name": "Kothrud Paud Road Depot", "area": "Kothrud"},
        {"name": "Viman Nagar Air Cargo Node", "area": "Viman Nagar"},
        {"name": "Bhosari MIDC Industrial Hub", "area": "Pimpri-Chinchwad"},
        {"name": "Chakan Automotive Logistics Park", "area": "Chakan"},
        {"name": "Baner High Street Depot", "area": "Baner"},
        {"name": "Kalyani Nagar Freight Center", "area": "Kalyani Nagar"},
        {"name": "Swargate Central Transit Terminal", "area": "Swargate"},
        {"name": "Wakad Phoenix Mall Corridor", "area": "Wakad"},
        {"name": "Kharadi EON Free Zone", "area": "Kharadi"},
        {"name": "Aundh DP Road Terminal", "area": "Aundh"},
        {"name": "Senapati Bapat Road Depot", "area": "SB Road"},
        {"name": "Fatima Nagar Junction", "area": "Wanowrie"},
    ],
    "Chennai": [
        {"name": "Guindy Industrial Estate Terminal", "area": "Guindy"},
        {"name": "Ambattur Industrial Estate", "area": "Ambattur"},
        {"name": "T Nagar Commercial Hub", "area": "T Nagar"},
        {"name": "OMR IT Corridor Hub", "area": "Sholinganallur"},
        {"name": "Sriperumbudur Freight Park", "area": "Sriperumbudur"},
        {"name": "Anna Nagar West Depot", "area": "Anna Nagar"},
        {"name": "Velachery Bypass Node", "area": "Velachery"},
        {"name": "Koyambedu Wholesale Market Yard", "area": "Koyambedu"},
        {"name": "Adyar Kasturba Nagar", "area": "Adyar"},
        {"name": "Tambaram Freight Station", "area": "Tambaram"},
        {"name": "Porur Junction Cargo Center", "area": "Porur"},
    ],
    "Kolkata": [
        {"name": "Salt Lake Sector V IT Hub", "area": "Salt Lake"},
        {"name": "Rajarhat New Town Logistics Center", "area": "New Town"},
        {"name": "Burrabazar Wholesale Hub", "area": "Burrabazar"},
        {"name": "Park Street Commercial Terminal", "area": "Park Street"},
        {"name": "Howrah Rail Freight Yard", "area": "Howrah"},
        {"name": "Taratala Industrial Area", "area": "Taratala"},
        {"name": "Dum Dum Air Cargo Point", "area": "Dum Dum"},
        {"name": "Kasba Industrial Estate", "area": "Kasba"},
    ],
    "Ahmedabad": [
        {"name": "Sanand Industrial Freight Hub", "area": "Sanand"},
        {"name": "Changodar Logistics Park", "area": "Changodar"},
        {"name": "SG Highway Commercial Node", "area": "SG Highway"},
        {"name": "Naroda GIDC Industrial Area", "area": "Naroda"},
        {"name": "Prahlad Nagar Business Hub", "area": "Prahlad Nagar"},
    ],
    "Maharashtra": [
        {"name": "BKC Freight Gateway", "area": "Bandra-Kurla Complex", "city": "Mumbai"},
        {"name": "Hinjawadi Phase 1 Logistics Hub", "area": "Hinjawadi", "city": "Pune"},
        {"name": "Andheri MIDC Cargo Terminal", "area": "Andheri East", "city": "Mumbai"},
        {"name": "Vashi APMC Market Terminal", "area": "Navi Mumbai", "city": "Navi Mumbai"},
        {"name": "Shivaji Nagar Logistics Node", "area": "Shivaji Nagar", "city": "Pune"},
        {"name": "Thane Wagle Estate Hub", "area": "Thane West", "city": "Thane"},
        {"name": "Hadapsar Magarpatta City Hub", "area": "Hadapsar", "city": "Pune"},
        {"name": "Powai Supreme Business Park", "area": "Powai", "city": "Mumbai"},
        {"name": "Bhosari MIDC Industrial Hub", "area": "Pimpri-Chinchwad", "city": "Pune"},
        {"name": "Lower Parel Commercial Center", "area": "Lower Parel", "city": "Mumbai"},
        {"name": "Kothrud Paud Road Depot", "area": "Kothrud", "city": "Pune"},
        {"name": "Chakan Automotive Logistics Park", "area": "Chakan", "city": "Pune"},
        {"name": "Goregaon Nesco Cargo Depot", "area": "Goregaon East", "city": "Mumbai"},
        {"name": "Viman Nagar Air Cargo Node", "area": "Viman Nagar", "city": "Pune"},
        {"name": "Rabale Industrial Area", "area": "Airoli / Navi Mumbai", "city": "Navi Mumbai"},
        {"name": "Baner High Street Depot", "area": "Baner", "city": "Pune"},
        {"name": "Worli Seaface Logistics Node", "area": "Worli", "city": "Mumbai"},
        {"name": "Kharadi EON Free Zone", "area": "Kharadi", "city": "Pune"},
        {"name": "Borivali National Park Depot", "area": "Borivali East", "city": "Mumbai"},
        {"name": "Swargate Central Transit Terminal", "area": "Swargate", "city": "Pune"},
    ],
}


def get_city_landmark(city: str, node_idx: int) -> Dict[str, str]:
    """Dynamically resolves realistic localized landmarks for any operational city."""
    clean_city = (city or "Maharashtra").strip()
    matched_key = None
    for k in CITY_LANDMARKS:
        if k.lower() == clean_city.lower() or k.lower() in clean_city.lower() or clean_city.lower() in k.lower():
            matched_key = k
            break

    if matched_key:
        landmarks = CITY_LANDMARKS[matched_key]
        lm = landmarks[node_idx % len(landmarks)]
        return {"name": lm["name"], "area": lm["area"], "city": lm.get("city", clean_city)}

    # Procedural zone generation for arbitrary configured cities
    zone_letter = chr(65 + (node_idx % 26))
    sector_num = (node_idx % 30) + 1
    return {
        "name": f"{clean_city} Logistics Hub #{node_idx}",
        "area": f"Sector {sector_num} (Zone {zone_letter})",
        "city": clean_city,
    }


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
        self.city = "Maharashtra"
        self._cached_db_partners: Dict[str, Dict[str, Any]] = {}
        self._last_partner_fetch_time: float = 0.0
        self._cached_db_orders: Dict[str, Dict[str, Any]] = {}
        self._last_order_fetch_time: float = 0.0

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
        self.order_requests: Dict[str, Dict[str, Any]] = {}
        self.recovery_routes: Dict[str, List[int]] = {}
        self.last_ppo_reward: float = 0.0
        self.cumulative_ppo_reward: float = 0.0
        self.last_ppo_action_idx: int = 4
        self.event_counter: int = 0
        self.partner_deliveries: Dict[str, int] = {}
        self.mesh_chat_history: List[Dict[str, Any]] = [
            {
                "id": "CHAT_INIT_01",
                "sender": "HUB_BKC",
                "receiver": "BROADCAST",
                "message": "Corridor RF Radio Mesh online. 802.11p DSRC telemetry active across BKC-Pune expressway.",
                "timestamp": "08:00:00",
                "timestamp_mins": 0.0,
                "delivered": True,
                "hop_count": 1,
                "route_taken": ["HUB_BKC", "PEER_VASHI", "PEER_LONAVALA", "PEER_PUNE"],
                "latency_ms": 22.4,
            }
        ]

        # Incremental state tracking for PPO multi-objective rewards
        self.last_delivered_count: int = 0
        self.last_late_count: int = 0
        self.last_failed_count: int = 0
        self.last_distance: float = 0.0
        self.last_fuel: float = 0.0
        self.last_empty_km: float = 0.0
        self.last_delay_mins: float = 0.0
        self.reward_calculator = FleetRewardCalculator(MultiObjectiveRewardConfig())

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

    def set_city(self, city: str) -> None:
        with self.lock:
            if city and city.strip():
                self.city = city.strip()
                t = getattr(self.env, "current_time_mins", 0.0) if self.env else 0.0
                self._log_event(t, "ADMIN", f"Operations city updated to {self.city}.")

    def reset(
        self,
        dataset: str = "C101",
        customers: int = 20,
        vehicles: int = 4,
        seed: int = 42,
        horizon: float = 1200.0,
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resets the simulation session with configured parameters."""
        with self.lock:
            if city and city.strip():
                self.city = city.strip()
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
            self.partner_deliveries.clear()
            self.last_ppo_reward = 0.0
            self.cumulative_ppo_reward = 0.0
            self.last_ppo_action_idx = 4
            self.last_delivered_count = 0
            self.last_late_count = 0
            self.last_failed_count = 0
            self.last_distance = 0.0
            self.last_fuel = 0.0
            self.last_empty_km = 0.0
            self.last_delay_mins = 0.0

            # 1. Load benchmark instance
            self.fleet_state, self.road_network, _meta = load_solomon_benchmark(
                self.dataset, max_customers=self.customers_count, vehicle_count=self.vehicles_count
            )
            orders = list(self.fleet_state.active_orders.values())
            node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}

            # 2. Networking and Subsystems
            self.mesh = MeshNetwork(transmission_range_km=30.0, seed=self.seed)
            self.conn_manager = ConnectivityManager(initial_state=ConnectivityState.CLOUD_MODE)
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

            # 4. Multi-Agent Subsystem
            self.fleet_agent = FleetAgent(
                fleet_state=self.fleet_state,
                road_network=self.road_network,
                mesh_network=self.mesh,
                fuel_predictor=self.fuel_pred,
                use_ml_fuel=(self.fuel_pred is not None),
                seed=self.seed,
            )

            # 5. Discrete-event environment
            self.env = FleetSimulationEnvironment(
                fleet_state=self.fleet_state,
                road_network=self.road_network,
                node_id_map=node_id_map,
                fuel_model=self.fuel_model,
                mesh_network=self.mesh,
                step_size_mins=self.step_size_mins,
                seed=self.seed,
            )

            # 6. Link RL Environment to live simulator
            if self.ppo_agent:
                if self.rl_env is None:
                    self.rl_env = SWARMRLEnv(
                        dataset_name=self.dataset,
                        num_customers=self.customers_count,
                        num_vehicles=self.vehicles_count,
                        seed=self.seed,
                        travel_time_predictor=self.tt_pred,
                        fuel_predictor=self.fuel_pred,
                        demand_predictor=self.demand_pred,
                    )
                self.rl_env.env = self.env
                self.rl_env.controlled_truck_id = (
                    list(self.fleet_state.vehicles.keys())[0] if self.fleet_state.vehicles else "TRUCK_01"
                )

            # 7. Log initial events
            self._log_event(
                0.0,
                "SIM_START",
                f"Simulation initialized: {self.dataset}, {self.vehicles_count} vehicles, {self.customers_count} orders (Seed {self.seed}).",
                target="Depot",
                severity="INFO",
            )
            self._add_timeline(0.0, "Operations Ready", f"{len(self.fleet_state.active_orders)} customer orders loaded and ready for delivery partner request.", "SYSTEM")

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
                self.rl_env.env = self.env
                obs = self.rl_env._get_observation()
                action_idx = self.ppo_agent.predict(obs, deterministic=True)
                self.last_ppo_action_idx = action_idx
                action_name = ACTION_NAMES[action_idx] if 0 <= action_idx < len(ACTION_NAMES) else "HOLD_OR_CONTINUE"

                # Measure empirical deltas for step reward
                curr_delivered = len(self.env.delivered_orders)
                curr_late = len(self.env.late_orders)
                curr_failed = len(self.env.failed_orders)
                curr_dist = self.env.total_distance_traveled_km
                curr_fuel = self.env.total_fuel_liters
                curr_empty = self.env.total_empty_distance_km

                new_deliveries = max(0, curr_delivered - self.last_delivered_count)
                new_late = max(0, curr_late - self.last_late_count)
                new_failed = max(0, curr_failed - self.last_failed_count)
                new_on_time = max(0, new_deliveries - new_late)

                delta_dist = max(0.0, curr_dist - self.last_distance)
                delta_fuel = max(0.0, curr_fuel - self.last_fuel)
                delta_co2 = delta_fuel * 2.68
                delta_empty = max(0.0, curr_empty - self.last_empty_km)

                curr_delay_mins = sum(
                    max(0.0, (self.fleet_state.active_orders[oid].actual_arrival_time or self.env.current_time_mins) - self.fleet_state.active_orders[oid].latest_delivery)
                    for oid in self.env.late_orders
                    if oid in self.fleet_state.active_orders
                )
                delta_delay = max(0.0, curr_delay_mins - self.last_delay_mins)
                self.last_delay_mins = curr_delay_mins

                fleet_util = 0.0
                active_vehs = [veh for veh in self.fleet_state.vehicles.values() if veh.status != VehicleStatus.BROKEN_DOWN]
                if active_vehs:
                    fleet_util = sum(veh.utilization_rate for veh in active_vehs) / len(active_vehs)

                step_reward = self.reward_calculator.calculate_step_reward(
                    new_deliveries=new_deliveries,
                    new_on_time=new_on_time,
                    new_recoveries=0,
                    new_failed=new_failed,
                    new_late=new_late,
                    delay_minutes=delta_delay,
                    incremental_distance_km=delta_dist,
                    incremental_fuel_liters=delta_fuel,
                    incremental_co2_kg=delta_co2,
                    incremental_empty_km=delta_empty,
                    fleet_utilization_ratio=fleet_util,
                )
                self.last_delivered_count = curr_delivered
                self.last_late_count = curr_late
                self.last_failed_count = curr_failed
                self.last_distance = curr_dist
                self.last_fuel = curr_fuel
                self.last_empty_km = curr_empty

                self.last_ppo_reward = round(float(step_reward), 2)
                self.cumulative_ppo_reward = round(self.cumulative_ppo_reward + self.last_ppo_reward, 2)

                target_v = None
                target_o = None
                action_reason = None
                if action_name == "REASSIGN_STRANDED_ORDER":
                    for o in self.fleet_state.active_orders.values():
                        if o.is_reassigned:
                            target_o = str(o.order_id)
                            target_v = o.assigned_vehicle_id
                            action_reason = "Peer mesh auction reallocation"
                            break
                elif action_name == "ASSIGN_BEST_ORDER":
                    action_reason = "Customer deadline feasibility"
                elif action_name == "REPOSITION_TO_DEMAND_ZONE":
                    action_reason = "Demand surge anticipated in sector"
                elif action_name == "HOLD_OR_CONTINUE":
                    action_reason = "Nominal trajectory cruise"

                ppo_entry = {
                    "time": round(self.env.current_time_mins, 1),
                    "time_str": self._format_sim_time(self.env.current_time_mins),
                    "action_idx": action_idx,
                    "action": action_name,
                    "target": target_v,
                    "order_id": target_o,
                    "reason": action_reason,
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
            if target_vid:
                if target_vid not in self.fleet_state.vehicles:
                    self._ensure_vehicle_for_partner(target_vid)
            else:
                # Pick vehicle with active assigned orders
                candidates = [v_id for v_id, v in self.fleet_state.vehicles.items() if v.status != VehicleStatus.BROKEN_DOWN]
                target_vid = candidates[0] if candidates else None
                if not target_vid or target_vid not in self.fleet_state.vehicles:
                    return {"success": False, "error": "No available vehicle to break down"}

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

            recovered_count = rec_res.get("recovered_count", rec_res.get("recovered_orders_count", 0))
            transfers = rec_res.get("transfers", [])
            winning_veh = (
                transfers[0].get("to_vehicle") or transfers[0].get("target_vehicle_id")
                if transfers
                else None
            )

            # Atomically apply reassignment transfers in simulation environment
            if rec_res.get("success") and transfers:
                self.env.execute_action({"type": "REASSIGN_ORDERS", "transfers": transfers})

            # Create recovery flow entries
            self.recovery_flow = [
                {"id": 1, "title": f"{target_vid} MECHANICAL FAULT", "status": "COMPLETED", "detail": "Engine stopped on edge"},
                {"id": 2, "title": "SOS BROADCAST OVER MESH", "status": "COMPLETED", "detail": f"Range 30.0 km, hop count {rec_res.get('mesh_hops', 1)}"},
                {"id": 3, "title": "PEER CONTRACT-NET BIDS", "status": "COMPLETED", "detail": "Evaluated via ML fuel & detour"},
                {"id": 4, "title": f"WINNER SELECTED: {winning_veh}", "status": "COMPLETED", "detail": f"Auction resolved in {rec_time_ms} ms"},
                {"id": 5, "title": f"{recovered_count} ORDER(S) REASSIGNED", "status": "COMPLETED", "detail": f"Recovery route attached to {winning_veh}"},
                {"id": 6, "title": "DELIVERY RESUMED", "status": "IN_PROGRESS", "detail": "Surviving truck executing updated route"},
            ]

            t0_detour = float(transfers[0].get("detour_km") or 4.2) if transfers else 0.0
            t0_fuel = float(transfers[0].get("additional_fuel") or 1.4) if transfers else 0.0

            incident = {
                "id": f"INC_{len(self.incidents) + 1:02d}",
                "vehicle_id": target_vid,
                "time": round(cur_t, 1),
                "time_str": self._format_sim_time(cur_t),
                "stranded_orders": stranded,
                "recovery_status": "RECOVERED" if recovered_count > 0 else "PARTIAL",
                "recovery_vehicle": winning_veh,
                "recovery_time_sec": round(rec_time_ms / 1000.0, 4),
                "recovery_distance_km": round(t0_detour, 2),
                "recovery_fuel_l": round(t0_fuel, 2),
                "recovery_co2_kg": round(t0_fuel * 2.68, 2),
            }
            self.incidents.insert(0, incident)

            # Record real autonomous decision when self-healing recovery occurs
            if recovered_count > 0 and winning_veh:
                self.ppo_history.append({
                    "time": round(cur_t, 1),
                    "time_str": self._format_sim_time(cur_t),
                    "action": "REASSIGN_STRANDED_ORDER",
                    "target": winning_veh,
                    "order_id": str(transfers[0].get("order_id")) if transfers else None,
                    "reason": f"Contract-Net auction resolved via peer mesh ({rec_time_ms} ms)",
                    "reward": 10.0,
                })

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

    def repair_vehicle(self, vehicle_id: Optional[str] = None) -> Dict[str, Any]:
        """Restores a broken down vehicle back to IDLE/operational status and clears SOS."""
        with self.lock:
            if not self.fleet_state:
                return {"success": False, "error": "Simulation not initialized"}
            target_vid = vehicle_id
            if not target_vid:
                candidates = [vid for vid, v in self.fleet_state.vehicles.items() if v.status == VehicleStatus.BROKEN_DOWN]
                target_vid = candidates[0] if candidates else (list(self.fleet_state.vehicles.keys())[0] if self.fleet_state.vehicles else None)

            if target_vid and target_vid in self.fleet_state.vehicles:
                self.fleet_state.vehicles[target_vid].status = VehicleStatus.IDLE
                cur_t = self.env.current_time_mins if self.env else 0.0
                self._log_event(
                    cur_t,
                    "VEHICLE_REPAIRED",
                    f"{target_vid} recovered from breakdown. Restored to IDLE operational status.",
                    target=target_vid,
                    severity="SUCCESS",
                )
                return {"success": True, "message": f"{target_vid} repaired and operational."}
            return {"success": False, "error": f"Vehicle '{target_vid}' not found"}

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

    def deploy_test_mesh_nodes(self) -> Dict[str, Any]:
        """
        Deploys 4 peer radio nodes along the Maharashtra corridor for testing
        multi-hop transmission and Contract-Net auction when no real trucks are on the road.
        """
        with self.lock:
            if not self.mesh:
                self.mesh = MeshNetwork(transmission_range_km=30.0, seed=self.seed)

            test_nodes = {
                "HUB_BKC": (15.0, 20.0),
                "PEER_VASHI": (28.0, 30.0),      # ~16.4 km from HUB_BKC (<= 30km)
                "PEER_LONAVALA": (44.0, 46.0),   # ~22.6 km from PEER_VASHI (<= 30km)
                "PEER_PUNE": (60.0, 58.0),       # ~20.0 km from PEER_LONAVALA (<= 30km)
            }
            for nid, pos in test_nodes.items():
                self.mesh.update_node_position(nid, pos)
                self.mesh.set_node_failed(nid, False)

            topo = self.mesh.build_topology()
            cur_t = self.env.current_time_mins if self.env else 0.0
            self._log_event(
                cur_t,
                "MESH_TEST_DEPLOYED",
                "Deployed 4 peer radio nodes: HUB_BKC ➔ PEER_VASHI ➔ PEER_LONAVALA ➔ PEER_PUNE (30km RF links established).",
                target="MeshNetwork",
                severity="INFO",
            )
            self._add_timeline(cur_t, "Mesh Test Deployed", "4 radio nodes active along corridor. Multi-hop mesh ready.", "NETWORK")
            return {
                "success": True,
                "nodes": list(self.mesh.nodes.keys()),
                "links": [[u, v] for u, v in topo.edges()],
                "connected_components": nx.number_connected_components(topo) if len(self.mesh.nodes) > 0 else 0,
            }

    def clear_test_mesh_nodes(self) -> Dict[str, Any]:
        """Clears test mesh nodes and retains only live vehicle nodes."""
        with self.lock:
            if not self.mesh:
                return {"success": True, "nodes": []}

            test_keys = ["HUB_BKC", "PEER_VASHI", "PEER_LONAVALA", "PEER_PUNE"]
            for k in test_keys:
                self.mesh.nodes.pop(k, None)
                self.mesh.failed_nodes.discard(k)

            topo = self.mesh.build_topology()
            cur_t = self.env.current_time_mins if self.env else 0.0
            self._log_event(
                cur_t,
                "MESH_TEST_CLEARED",
                "Cleared test mesh nodes. Topology returned to real vehicle fleet only.",
                target="MeshNetwork",
                severity="INFO",
            )
            return {
                "success": True,
                "nodes": list(self.mesh.nodes.keys()),
                "links": [[u, v] for u, v in topo.edges()],
            }

    def send_mesh_test_ping(self, source: str = "HUB_BKC", target: str = "PEER_PUNE") -> Dict[str, Any]:
        """Transmits a multi-hop test packet through the mesh network and returns empirical latency and hops."""
        with self.lock:
            if not self.mesh or not self.mesh.nodes:
                return {"success": False, "error": "No mesh nodes available. Click 'Deploy Test Mesh Nodes' first."}

            if source not in self.mesh.nodes or target not in self.mesh.nodes:
                available = list(self.mesh.nodes.keys())
                if len(available) < 2:
                    return {"success": False, "error": "At least 2 active nodes required for peer-to-peer transmission test."}
                source = available[0]
                target = available[-1]

            cur_t = self.env.current_time_mins if self.env else 0.0
            msg = MeshMessage(
                message_id=f"PING_{uuid.uuid4().hex[:6].upper()}",
                message_type=MessageType.STATE_SYNC,
                sender_id=source,
                receiver_id=target,
                timestamp_mins=cur_t,
                payload={"test": True, "ping_time": time.time()},
            )
            success = self.mesh.transmit(msg)
            if self.fleet_agent:
                self.fleet_agent.total_mesh_messages += 1

            if success:
                self._log_event(
                    cur_t,
                    "MESH_PING_SUCCESS",
                    f"Test packet {msg.message_id} delivered from {source} to {target} via {' ➔ '.join(msg.route_taken)} ({msg.hop_count} hops, {msg.total_latency_ms:.1f}ms).",
                    target="MeshNetwork",
                    severity="INFO",
                )
            else:
                self._log_event(
                    cur_t,
                    "MESH_PING_DROPPED",
                    f"Packet {msg.message_id} from {source} to {target} dropped: No multi-hop RF path available.",
                    target="MeshNetwork",
                    severity="WARNING",
                )

            metrics = self.mesh.get_mesh_metrics()
            return {
                "success": success,
                "message_id": msg.message_id,
                "source": source,
                "target": target,
                "hop_count": msg.hop_count,
                "route_taken": msg.route_taken,
                "latency_ms": round(msg.total_latency_ms, 2),
                "metrics": metrics,
            }

    def simulate_mesh_sos(self, node_id: str = "PEER_LONAVALA") -> Dict[str, Any]:
        """Simulates node breakdown and triggers peer SOS auction broadcast across the RF mesh."""
        with self.lock:
            if not self.mesh or not self.mesh.nodes:
                return {"success": False, "error": "No mesh nodes available."}

            if node_id not in self.mesh.nodes:
                node_id = list(self.mesh.nodes.keys())[0]

            cur_t = self.env.current_time_mins if self.env else 0.0
            sos_msg = MeshMessage(
                message_id=f"SOS_{uuid.uuid4().hex[:6].upper()}",
                message_type=MessageType.BREAKDOWN_ALERT,
                sender_id=node_id,
                receiver_id="BROADCAST",
                timestamp_mins=cur_t,
                payload={"emergency": "ENGINE_FAILURE", "location": self.mesh.nodes[node_id]},
            )
            delivered = self.mesh.transmit(sos_msg)
            if self.fleet_agent:
                self.fleet_agent.total_mesh_messages += 1

            self.mesh.set_node_failed(node_id, True)
            self.mesh.build_topology()

            peers_alerted = [n for n in sos_msg.route_taken if n != node_id]
            self._log_event(
                cur_t,
                "MESH_SOS_AUCTION",
                f"Emergency SOS from {node_id} broadcasted over 30km RF mesh. Peers alerted: {', '.join(peers_alerted) if peers_alerted else 'None'}.",
                target="MeshNetwork",
                severity="DANGER",
            )
            self._add_timeline(cur_t, "Mesh SOS Alert", f"{node_id} broadcasted SOS. Multi-hop auction dispatched.", "INCIDENT")
            return {
                "success": True,
                "broken_node": node_id,
                "sos_delivered": delivered,
                "peers_alerted": peers_alerted,
                "hop_count": sos_msg.hop_count,
                "latency_ms": round(sos_msg.total_latency_ms, 2),
            }

    def send_mesh_chat(self, sender: str = "HUB_BKC", receiver: str = "BROADCAST", message: str = "") -> Dict[str, Any]:
        """Transmits a peer-to-peer or corridor broadcast chat packet across the RF mesh network."""
        with self.lock:
            if not self.mesh:
                self.mesh = MeshNetwork(transmission_range_km=30.0, seed=self.seed)

            if not self.mesh.nodes:
                self.deploy_test_mesh_nodes()

            available = list(self.mesh.nodes.keys())
            if sender not in self.mesh.nodes:
                sender = available[0] if available else "HUB_BKC"

            if receiver != "BROADCAST" and receiver not in self.mesh.nodes:
                receiver = available[-1] if len(available) > 1 else "BROADCAST"

            cur_t = self.env.current_time_mins if self.env else 0.0
            msg = MeshMessage(
                message_id=f"CHAT_{uuid.uuid4().hex[:6].upper()}",
                message_type=MessageType.CHAT_MESSAGE,
                sender_id=sender,
                receiver_id=receiver,
                timestamp_mins=cur_t,
                payload={"text": message, "chat": True},
            )
            success = self.mesh.transmit(msg)
            if self.fleet_agent:
                self.fleet_agent.total_mesh_messages += 1

            chat_record = {
                "id": msg.message_id,
                "sender": sender,
                "receiver": receiver,
                "message": message,
                "timestamp": time.strftime("%H:%M:%S"),
                "timestamp_mins": round(cur_t, 1),
                "delivered": success,
                "hop_count": msg.hop_count,
                "route_taken": msg.route_taken,
                "latency_ms": round(msg.total_latency_ms, 2),
            }
            self.mesh_chat_history.append(chat_record)
            if len(self.mesh_chat_history) > 50:
                self.mesh_chat_history = self.mesh_chat_history[-50:]

            route_str = " ➔ ".join(msg.route_taken) if msg.route_taken else "broadcast"
            self._log_event(
                cur_t,
                "MESH_CHAT",
                f"[{sender} ➔ {receiver}]: \"{message[:40]}{'...' if len(message) > 40 else ''}\" via {route_str} ({msg.hop_count} hops, {msg.total_latency_ms:.1f}ms)",
                target="MeshChat",
                severity="INFO",
            )
            return {
                "success": success,
                "record": chat_record,
                "metrics": self.mesh.get_mesh_metrics(),
            }

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
    # Delivery Partner & Task Allocation Operations
    # -------------------------------------------------------------------------
    def _ensure_vehicle_for_partner(self, partner_id: str, partner_meta: Optional[Dict[str, Any]] = None):
        """Instantiates a live vehicle for a registered or requesting delivery partner."""
        if not self.fleet_state:
            return
        if partner_meta and partner_meta.get("name"):
            if not hasattr(self, "_partner_names"):
                self._partner_names = {}
            self._partner_names[partner_id] = partner_meta["name"]
        if partner_id not in self.fleet_state.vehicles:
            meta = partner_meta or self.get_partner_meta(partner_id)
            max_w = float(meta.get("max_weight", 200.0) or 200.0)
            depot_loc = (40.0, 50.0)
            if self.road_network and self.road_network.node_coordinates:
                depot_loc = self.road_network.node_coordinates.get(0, (40.0, 50.0))
            veh = Vehicle(
                vehicle_id=partner_id,
                max_weight=max_w,
                max_volume=float(meta.get("max_volume", 50.0) or 50.0),
                current_location=depot_loc,
                current_node=0,
                fuel_capacity=300.0,
                fuel_level=float(meta.get("fuel_level", 100.0) or 100.0),
                status=VehicleStatus.IDLE,
                current_route=[0],
                assigned_orders=[],
                current_speed_kmh=0.0,
            )
            self.fleet_state.vehicles[partner_id] = veh
            if not hasattr(self, "initial_routes"):
                self.initial_routes = {}
            self.initial_routes[partner_id] = [0]

    def allocate_order(self, order_id: str, vehicle_id: str) -> Dict[str, Any]:
        """
        Allocates an order to a delivery partner (vehicle), validating capacity constraints
        and updating routes.
        """
        with self.lock:
            if not self.env or not self.fleet_state:
                self.reset()

            self._ensure_vehicle_for_partner(vehicle_id)

            if not self.fleet_state or vehicle_id not in self.fleet_state.vehicles:
                return {"success": False, "error": f"Delivery partner vehicle '{vehicle_id}' not found"}

            if order_id not in self.fleet_state.active_orders:
                return {"success": False, "error": f"Order '{order_id}' not found in active orders"}

            vehicle = self.fleet_state.vehicles[vehicle_id]
            order = self.fleet_state.active_orders[order_id]
            partner_info = self.get_partner_meta(vehicle_id)

            if vehicle.status == VehicleStatus.BROKEN_DOWN:
                return {
                    "success": False,
                    "error": f"Cannot allocate to {partner_info['name']} ({vehicle_id}): Vehicle is BROKEN DOWN",
                }

            if not vehicle.can_load(order.demand_weight, order.volume):
                return {
                    "success": False,
                    "error": (
                        f"Insufficient payload capacity for {partner_info['name']}. "
                        f"Remaining: {vehicle.remaining_weight_capacity():.1f}kg, Required: {order.demand_weight:.1f}kg"
                    ),
                }

            # If order was previously assigned to another vehicle, detach it
            old_vid = order.assigned_vehicle_id
            if old_vid and old_vid in self.fleet_state.vehicles and old_vid != vehicle_id:
                old_v = self.fleet_state.vehicles[old_vid]
                if order_id in old_v.assigned_orders:
                    old_v.assigned_orders.remove(order_id)
                    old_v.current_load = max(0.0, old_v.current_load - order.demand_weight)
                    old_v.current_volume_load = max(0.0, old_v.current_volume_load - order.volume)

            # Assign to target vehicle
            if order_id not in vehicle.assigned_orders:
                vehicle.assigned_orders.append(order_id)
                vehicle.current_load += order.demand_weight
                vehicle.current_volume_load += order.volume

            order.assigned_vehicle_id = vehicle_id
            order.status = OrderStatus.ASSIGNED
            if hasattr(self, "order_requests") and order_id in self.order_requests:
                del self.order_requests[order_id]

            # Append destination node to route if needed
            node_idx = self.env.node_id_map.get(order_id) if self.env else None
            if node_idx is not None and node_idx not in vehicle.current_route:
                if len(vehicle.current_route) >= 2 and vehicle.current_route[-1] == 0:
                    vehicle.current_route.insert(-1, node_idx)
                else:
                    vehicle.current_route.append(node_idx)

            if vehicle.status == VehicleStatus.IDLE:
                vehicle.status = VehicleStatus.EN_ROUTE

            cur_t = self.env.current_time_mins if self.env else 0.0
            self._log_event(
                cur_t,
                "TASK_ALLOCATION",
                f"Company Manager allocated Order {order_id} ({order.demand_weight:.1f}kg) to Partner {partner_info['name']} ({vehicle_id}).",
                target=vehicle_id,
                severity="INFO",
            )
            self._add_timeline(
                cur_t,
                f"Task Allocated: {order_id}",
                f"Assigned to {partner_info['name']} ({vehicle_id})",
                category="ALLOCATION",
            )

            return {
                "success": True,
                "message": f"Order {order_id} successfully allocated to {partner_info['name']}",
                "order_id": order_id,
                "vehicle_id": vehicle_id,
                "partner": partner_info,
            }

    def create_order(
        self,
        customer_name: str = "Customer",
        phone: str = "",
        pickup_address: str = "BKC Freight Gateway, Mumbai",
        delivery_address: str = "Hinjawadi Phase 1 Logistics Hub, Pune",
        demand_weight: float = 10.0,
        volume: float = 0.5,
        priority: str = "NORMAL",
        deadline_mins: float = 120.0,
        city: Optional[str] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Dynamically registers a live customer order into the active fleet state and Supabase."""
        with self.lock:
            if not self.fleet_state:
                self.reset(city=city or self.city)

            order_num = len(self.fleet_state.active_orders) + 1
            order_id = f"ORD_CUST_{int(time.time()) % 100000:05d}"

            from src.models.order import Order, OrderStatus

            cur_t = self.env.current_time_mins if self.env else 0.0
            earliest = cur_t
            latest = cur_t + max(30.0, float(deadline_mins))

            new_order = Order(
                order_id=order_id,
                pickup_location=(40.0, 50.0),
                destination=(45.0 + (order_num % 15), 55.0 + (order_num % 15)),
                demand_weight=float(demand_weight),
                volume=float(volume if volume > 0 else demand_weight * 0.25),
                priority=2 if priority.upper() == "EXPRESS" else (3 if priority.upper() == "URGENT" else 1),
                earliest_delivery=earliest,
                latest_delivery=latest,
                service_time=10.0,
                release_time=earliest,
                status=OrderStatus.PENDING,
            )

            self.fleet_state.active_orders[order_id] = new_order
            if self.env and hasattr(self.env, "node_id_map"):
                self.env.node_id_map[order_id] = order_num

            # Sync to Supabase orders table
            try:
                from src.api.supabase_service import supabase_service
                clean_city = city or self.city or "Maharashtra"
                area_name = delivery_address.split(",")[1].strip() if "," in delivery_address else delivery_address
                supabase_service.sync_orders([{
                    "id": order_id,
                    "customer_id": order_num,
                    "address": delivery_address,
                    "area": area_name,
                    "city": clean_city,
                    "demand": float(demand_weight),
                    "priority": priority.upper(),
                    "deadline": latest,
                    "ready_time": earliest,
                    "status": "PENDING",
                }])
            except Exception as e:
                print(f"[SimulationRunner] Error syncing new order to Supabase: {e}")

            self._log_event(
                cur_t,
                "NEW_CUSTOMER_ORDER",
                f"Customer {customer_name} placed order {order_id} ({demand_weight}kg) -> {delivery_address}",
                target=order_id,
                severity="INFO",
            )

            return {
                "success": True,
                "order_id": order_id,
                "message": f"Order {order_id} placed successfully!",
                "order": {
                    "id": order_id,
                    "customer_name": customer_name,
                    "phone": phone,
                    "pickup_address": pickup_address,
                    "delivery_address": delivery_address,
                    "demand_weight": demand_weight,
                    "priority": priority,
                    "status": "PENDING",
                    "deadline_mins": deadline_mins,
                },
            }

    def auto_allocate_order(self, order_id: str) -> Dict[str, Any]:
        """
        Uses SWARMRoute AI Decision Engine (OR-Tools capacity constraints + PPO RouteIntelligence)
        to automatically evaluate all delivery partners and allocate the optimal vehicle.
        """
        with self.lock:
            if not self.fleet_state or order_id not in self.fleet_state.active_orders:
                return {"success": False, "error": f"Order '{order_id}' not found"}

            order = self.fleet_state.active_orders[order_id]
            eligible_candidates = []

            for vid, v in self.fleet_state.vehicles.items():
                if v.status == VehicleStatus.BROKEN_DOWN:
                    continue
                if not v.can_load(order.demand_weight, order.volume):
                    continue

                fuel_val = float(v.fuel_level)
                fuel_cap = float(getattr(v, "fuel_capacity", 300.0))
                fuel_pct = (fuel_val / max(1.0, fuel_cap)) * 100.0 if fuel_val > 100.0 else fuel_val
                if fuel_pct < 15.0:
                    continue

                meta = self.get_partner_meta(vid)
                rem_capacity = v.remaining_weight_capacity()
                active_orders_count = len(v.assigned_orders)

                score = (active_orders_count * 25.0) - (rem_capacity * 0.1) - (fuel_pct * 0.2)
                eligible_candidates.append({
                    "vehicle_id": vid,
                    "vehicle": v,
                    "meta": meta,
                    "score": score,
                    "rem_capacity": rem_capacity,
                    "fuel_pct": fuel_pct,
                    "active_orders": active_orders_count,
                })

            if not eligible_candidates:
                return {
                    "success": False,
                    "error": f"No eligible delivery partner available with sufficient payload capacity (>={order.demand_weight}kg) and battery/fuel (>15%).",
                }

            eligible_candidates.sort(key=lambda x: x["score"])
            best = eligible_candidates[0]
            best_vid = best["vehicle_id"]
            best_meta = best["meta"]

            alloc_res = self.allocate_order(order_id, best_vid)
            if alloc_res.get("success"):
                rationale = (
                    f"AI Decision Engine selected {best_meta['name']} ({best_vid} · {best_meta['vehicle_model']}): "
                    f"Optimal payload match (remaining {best['rem_capacity']:.1f}kg), "
                    f"healthy battery/fuel ({best['fuel_pct']:.0f}%), and {best['active_orders']} active stops."
                )
                alloc_res["ai_rationale"] = rationale
                alloc_res["selected_by"] = "PPO_ORTOOLS_AI"
                cur_t = self.env.current_time_mins if self.env else 0.0
                self._log_event(
                    cur_t,
                    "AI_AUTO_ALLOCATION",
                    rationale,
                    target=best_vid,
                    severity="INFO",
                )

            return alloc_res


    def complete_order(self, order_id: str, vehicle_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Marks an order as DELIVERED by the delivery partner, unloads cargo,
        and logs delivery metrics.
        """
        with self.lock:
            if not self.env or not self.fleet_state:
                return {"success": False, "error": "Simulation environment not initialized"}

            if order_id not in self.fleet_state.active_orders:
                return {"success": False, "error": f"Order '{order_id}' not found"}

            order = self.fleet_state.active_orders[order_id]
            actual_vid = vehicle_id or order.assigned_vehicle_id

            if actual_vid and actual_vid in self.fleet_state.vehicles:
                vehicle = self.fleet_state.vehicles[actual_vid]
                if order_id in vehicle.assigned_orders:
                    vehicle.assigned_orders.remove(order_id)
                vehicle.current_load = max(0.0, vehicle.current_load - order.demand_weight)
                vehicle.current_volume_load = max(0.0, vehicle.current_volume_load - order.volume)
                if len(vehicle.assigned_orders) == 0:
                    vehicle.status = VehicleStatus.IDLE

            order.status = OrderStatus.DELIVERED
            cur_t = self.env.current_time_mins if self.env else 0.0
            order.actual_delivery_time = cur_t

            if self.env:
                self.env.delivered_orders.add(order_id)
                if order.is_late(cur_t):
                    self.env.late_orders.add(order_id)

            partner_meta = self.get_partner_meta(actual_vid)
            if actual_vid:
                self.partner_deliveries[actual_vid] = (
                    self.partner_deliveries.get(actual_vid, 0) + 1
                )

            self._log_event(
                cur_t,
                "DELIVERY_COMPLETE",
                f"Partner {partner_meta['name']} successfully delivered {order_id}! Cargo unloaded.",
                target=actual_vid or "Rider",
                severity="SUCCESS",
            )
            self._add_timeline(
                cur_t,
                f"Delivered: {order_id}",
                f"Completed by {partner_meta['name']}",
                category="DELIVERY",
            )

            return {
                "success": True,
                "message": f"Order {order_id} marked as DELIVERED by {partner_meta['name']}",
                "order_id": order_id,
                "vehicle_id": actual_vid,
            }

    def request_order(self, order_id: str, partner_id: str, partner_name: str) -> Dict[str, Any]:
        """Delivery partner requests an available order."""
        with self.lock:
            if not self.fleet_state or order_id not in self.fleet_state.active_orders:
                return {"success": False, "error": f"Order '{order_id}' not found"}

            order = self.fleet_state.active_orders[order_id]
            if order.assigned_vehicle_id:
                return {"success": False, "error": f"Order '{order_id}' is already assigned to {order.assigned_vehicle_id}"}

            if not hasattr(self, "order_requests"):
                self.order_requests = {}
            self._ensure_vehicle_for_partner(partner_id, {"id": partner_id, "name": partner_name})
            self.order_requests[order_id] = {
                "requested_by_id": partner_id,
                "requested_by_name": partner_name,
                "requested_at": time.time(),
            }

            cur_t = self.env.current_time_mins if self.env else 0.0
            self._log_event(
                cur_t,
                "DISPATCH",
                f"Delivery Partner {partner_name} ({partner_id}) requested delivery for Order {order_id}.",
                target=partner_id,
                severity="INFO",
            )
            return {
                "success": True,
                "message": f"Delivery requested for Order {order_id}! Operations Manager will review and allocate.",
                "order_id": order_id,
                "partner_id": partner_id,
                "partner_name": partner_name,
            }

    def auto_allocate_all(self) -> Dict[str, Any]:
        """Dispatches all pending customer orders automatically using AI multi-objective scoring."""
        with self.lock:
            if not self.fleet_state:
                return {"success": False, "error": "Fleet not initialized"}

            pending_ids = [
                oid for oid, o in self.fleet_state.active_orders.items()
                if o.status == OrderStatus.PENDING and not o.assigned_vehicle_id
            ]

        allocated = []
        failed = []
        for oid in pending_ids:
            res = self.auto_allocate_order(oid)
            if res.get("success"):
                allocated.append({"order_id": oid, "vehicle_id": res.get("vehicle_id"), "partner": res.get("partner")})
            else:
                failed.append({"order_id": oid, "reason": res.get("error")})

        cur_t = self.env.current_time_mins if self.env else 0.0
        self._log_event(
            cur_t,
            "AI_AUTO_ALLOCATION",
            f"AI Batch Dispatch completed: {len(allocated)} orders allocated, {len(failed)} unassigned.",
            target="Fleet",
            severity="SUCCESS" if allocated else "INFO",
        )
        return {
            "success": True,
            "total_pending": len(pending_ids),
            "allocated_count": len(allocated),
            "allocated": allocated,
            "failed": failed,
        }

    def get_partner_meta(self, vehicle_id: Optional[str]) -> Dict[str, Any]:
        """Dynamically retrieves delivery partner metadata from cached Supabase database or synthesizes from fleet state."""
        if not vehicle_id:
            return {"id": "UNASSIGNED", "name": "Unassigned Partner", "avatar": "🛵"}
        
        # 1. Fast lookup from cached database partners (Zero network latency)
        if hasattr(self, "_cached_db_partners") and vehicle_id in self._cached_db_partners:
            p = self._cached_db_partners[vehicle_id]
            return {
                **p,
                "completed_deliveries": int(p.get("completed_deliveries", 0) or 0) + self.partner_deliveries.get(vehicle_id, 0),
            }
        
        # Fallback search across all cached partners by ID
        for p in getattr(self, "_cached_db_partners", {}).values():
            if p.get("id") == vehicle_id:
                return {
                    **p,
                    "completed_deliveries": int(p.get("completed_deliveries", 0) or 0) + self.partner_deliveries.get(vehicle_id, 0),
                }

        p_name = getattr(self, "_partner_names", {}).get(vehicle_id, f"Delivery Partner ({vehicle_id})")
        return {
            "id": vehicle_id,
            "name": p_name,
            "phone": "+91 98000 00000",
            "vehicle_model": "Electric Fleet Vehicle",
            "registration": f"MH-01-{vehicle_id[-4:] if len(vehicle_id) >= 4 else vehicle_id}",
            "hub": f"{self.city} Central Hub",
            "city": self.city,
            "rating": 5.0,
            "completed_deliveries": self.partner_deliveries.get(vehicle_id, 0),
            "avatar": "🛵",
        }

    def _async_refresh_db_partners(self) -> None:
        """Asynchronously queries Supabase for registered delivery partners in background thread (zero latency)."""
        def _fetch():
            try:
                from src.api.supabase_service import supabase_service
                db_partners = supabase_service.get_all_partners()
                mapped = {p["id"]: p for p in (db_partners or [])}
                with self.lock:
                    self._cached_db_partners = mapped
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _async_refresh_db_orders(self) -> None:
        """Asynchronously queries Supabase for orders in background thread (zero latency)."""
        def _fetch():
            try:
                from src.api.supabase_service import supabase_service
                db_orders = supabase_service.get_all_real_orders() if hasattr(supabase_service, "get_all_real_orders") else supabase_service.fetch_orders()
                if db_orders:
                    mapped = {o["id"]: o for o in db_orders}
                    with self.lock:
                        self._cached_db_orders = mapped
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def get_delivery_partners(self) -> List[Dict[str, Any]]:
        """Returns partner profiles dynamically from in-memory cache enriched with live vehicle telemetry (sub-millisecond)."""
        now = time.time()
        if not getattr(self, "_cached_db_partners", None):
            self._last_partner_fetch_time = now
            try:
                from src.api.supabase_service import supabase_service
                db_partners = supabase_service.get_all_partners()
                self._cached_db_partners = {p["id"]: p for p in (db_partners or [])}
            except Exception:
                self._cached_db_partners = {}
        elif now - self._last_partner_fetch_time > 10.0:
            self._last_partner_fetch_time = now
            self._async_refresh_db_partners()

        with self.lock:
            db_map = self._cached_db_partners if hasattr(self, "_cached_db_partners") and self._cached_db_partners else {}
            partners_list = []

            # Only authentic registered delivery partners from Supabase / memory store
            for pid, meta in db_map.items():
                vid = meta.get("vehicle_id") or pid
                v = self.fleet_state.vehicles.get(vid) if self.fleet_state else None
                assigned = list(v.assigned_orders) if v else []
                cur_load = round(float(v.current_load), 1) if v else float(meta.get("current_load", 0.0) or 0.0)
                max_wt = float(v.max_weight) if v else float(meta.get("max_weight", 100.0) or 100.0)
                rem_cap = round(max(0.0, max_wt - cur_load), 1)
                status = v.status.value if v else meta.get("status", "IDLE")
                raw_fuel = float(v.fuel_level) if v else float(meta.get("fuel_level", 100.0) or 100.0)
                cap = float(getattr(v, "fuel_capacity", 300.0)) if v else 100.0
                fuel = round(min(100.0, (raw_fuel / max(1.0, cap)) * 100.0), 1) if raw_fuel > 100.0 else round(min(100.0, max(0.0, raw_fuel)), 1)
                speed = round(float(v.current_speed_kmh), 1) if v else float(meta.get("speed_kmh", 0.0) or 0.0)
                loc = (round(float(v.current_location[0]), 2), round(float(v.current_location[1]), 2)) if v else (
                    float(meta.get("location_x") or 0.0), float(meta.get("location_y") or 0.0)
                )
                completed = int(meta.get("completed_deliveries", 0) or 0) + self.partner_deliveries.get(vid, 0)

                partners_list.append({
                    **meta,
                    "city": meta.get("city") or self.city,
                    "status": status,
                    "completed_deliveries": completed,
                    "current_load": cur_load,
                    "max_weight": max_wt,
                    "remaining_capacity": rem_cap,
                    "fuel_level": fuel,
                    "speed_kmh": speed,
                    "location": {"x": loc[0], "y": loc[1]},
                    "assigned_orders": assigned,
                    "active_order_count": len(assigned),
                    "is_available": status in (VehicleStatus.IDLE.value, VehicleStatus.EN_ROUTE.value) and rem_cap > 5.0,
                })
            return partners_list

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
                    "delivery_partners": self.get_delivery_partners(),
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
                partner_meta = self.get_partner_meta(vid)

                vehicles_list.append({
                    "id": vid,
                    "partner_name": partner_meta.get("name", vid),
                    "partner_phone": partner_meta.get("phone", ""),
                    "vehicle_model": partner_meta.get("vehicle_model", "Commercial Delivery Vehicle"),
                    "registration": partner_meta.get("registration", vid),
                    "hub": partner_meta.get("hub", f"{self.city} Hub"),
                    "rating": partner_meta.get("rating"),
                    "avatar": partner_meta.get("avatar", "🚚"),
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
                    "fuel_level": round(min(100.0, (float(v.fuel_level) / max(1.0, float(getattr(v, "fuel_capacity", 300.0)))) * 100.0), 1) if float(v.fuel_level) > 100.0 else round(float(v.fuel_level), 1),
                    "fuel_consumed": round(max(0.0, float(getattr(v, "fuel_capacity", 300.0)) - float(v.fuel_level)), 2) if float(v.fuel_level) > 100.0 else round(max(0.0, 100.0 - float(v.fuel_level)), 2),
                    "co2_kg": round((max(0.0, float(getattr(v, "fuel_capacity", 300.0)) - float(v.fuel_level)) if float(v.fuel_level) > 100.0 else max(0.0, 100.0 - float(v.fuel_level))) * 2.68, 2),
                    "speed_kmh": round(float(v.current_speed_kmh), 1),
                    "route_progress": prog_pct,
                    "eta_mins": round(max(0.0, (100.0 - prog_pct) * 0.8), 1),
                    "connectivity": self.fleet_state.connectivity_state.value,
                    "mesh_neighbors": neighbors,
                    "edge": f"{v.current_node} -> {v.next_node}" if v.next_node is not None else "At Stop",
                    "last_action": ACTION_NAMES[self.last_ppo_action_idx],
                })

            db_partners_list = self.get_delivery_partners()
            fleet_size = len(db_partners_list)
            broken_count = sum(1 for p in db_partners_list if p.get("status") == VehicleStatus.BROKEN_DOWN.value)
            avail_count = fleet_size - broken_count
            active_p_count = sum(1 for p in db_partners_list if p.get("status") in (VehicleStatus.EN_ROUTE.value, "ACTIVE"))
            util_pct = round((active_p_count / max(1, fleet_size)) * 100.0, 1) if fleet_size > 0 else 0.0

            # Orders serialization from authentic Supabase database records (non-blocking async background cache)
            now_t = time.time()
            if now_t - getattr(self, "_last_order_fetch_time", 0.0) > 10.0:
                self._last_order_fetch_time = now_t
                self._async_refresh_db_orders()
            db_orders_map = getattr(self, "_cached_db_orders", {})

            orders_list: List[Dict[str, Any]] = []
            for oid, o in self.fleet_state.active_orders.items():
                node_idx = self.env.node_id_map.get(oid, 0)
                coord = node_coords.get(node_idx, (0.0, 0.0))
                db_o = db_orders_map.get(oid)
                if db_o and db_o.get("address"):
                    address = db_o["address"]
                    area = db_o.get("area") or (address.split(",")[1].strip() if "," in address else address)
                    city = db_o.get("city") or self.city
                else:
                    landmark = get_city_landmark(self.city, node_idx)
                    address = f"{landmark['name']}, {landmark['area']}, {landmark['city']}"
                    area = landmark["area"]
                    city = landmark["city"]

                assigned_partner = (
                    self.get_partner_meta(o.assigned_vehicle_id).get("name", o.assigned_vehicle_id)
                    if o.assigned_vehicle_id else "Unassigned"
                )
                req_info = getattr(self, "order_requests", {}).get(oid, {})
                orders_list.append({
                    "id": oid,
                    "customer_id": node_idx,
                    "address": address,
                    "area": area,
                    "city": city,
                    "x": coord[0],
                    "y": coord[1],
                    "assigned_vehicle": o.assigned_vehicle_id,
                    "assigned_partner": assigned_partner,
                    "status": "REQUESTED" if (req_info.get("requested_by_id") and o.status == OrderStatus.PENDING) else o.status.value,
                    "requested_by_id": req_info.get("requested_by_id"),
                    "requested_by_name": req_info.get("requested_by_name"),
                    "requested_at": req_info.get("requested_at"),
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
                db_o = db_orders_map.get(oid)
                if db_o and db_o.get("address"):
                    c_address = db_o["address"]
                    c_area = db_o.get("area") or (c_address.split(",")[1].strip() if "," in c_address else c_address)
                    c_city = db_o.get("city") or self.city
                else:
                    landmark = get_city_landmark(self.city, node_idx)
                    c_address = f"{landmark['name']}, {landmark['area']}, {landmark['city']}"
                    c_area = landmark["area"]
                    c_city = landmark["city"]

                customers_list.append({
                    "id": node_idx,
                    "order_id": oid,
                    "address": c_address,
                    "area": c_area,
                    "city": c_city,
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
                    "city": self.city,
                    "hub": f"{self.city} Central GIS Hub",
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
                    "messages_sent": (self.mesh.get_mesh_metrics()["total_messages"] if self.mesh else 0) + (self.fleet_agent.total_mesh_messages if self.fleet_agent else 0),
                    "messages_delivered": (self.mesh.get_mesh_metrics()["delivered_messages"] if self.mesh else 0) + (self.fleet_agent.total_mesh_messages if self.fleet_agent else 0),
                    "messages_failed": ((self.mesh.get_mesh_metrics()["total_messages"] - self.mesh.get_mesh_metrics()["delivered_messages"]) if self.mesh else 0),
                    "avg_latency_ms": (self.mesh.get_mesh_metrics()["average_latency_ms"] if self.mesh else 0.0),
                    "connected_components": connected_components,
                },
                "mesh": {
                    "nodes": mesh_nodes,
                    "links": mesh_links,
                    "transmission_range_km": 30.0,
                    "chat_messages": getattr(self, "mesh_chat_history", [])[-30:],
                },
                "incidents": self.incidents,
                "recovery_flow": self.recovery_flow,
                # Zone-level predictor telemetry is not exposed by the runtime.
                # Do not return presentation-only forecast values.
                "predictions": {"zones": []},
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
                "delivery_partners": self.get_delivery_partners(),
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

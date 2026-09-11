from __future__ import annotations
import copy
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import numpy as np

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.order import Order, OrderStatus
from src.models.road import RoadNetwork, TrafficLevel
from src.data.loaders.solomon import load_solomon_benchmark
from src.simulation.events import FleetEvent, EventType


class DisruptionSpec(BaseModel):
    """Specification of an injected disruption event."""
    event_id: str
    event_type: str  # "BREAKDOWN", "CONNECTIVITY_LOSS", "TRAFFIC_SPIKE", "URGENT_ORDERS"
    timestamp_mins: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class BenchmarkScenario:
    """
    Standardized, self-contained benchmark scenario.
    Provides identical initial fleet, road network, orders, and disruption events
    to every evaluated algorithm.
    """
    def __init__(
        self,
        scenario_id: str,
        seed: int,
        dataset_name: str,
        customers_count: int,
        vehicles_count: int,
        simulation_duration_mins: float,
        step_size_mins: float,
        base_fleet: FleetState,
        base_road: RoadNetwork,
        node_id_map: Dict[str, int],
        disruptions: List[DisruptionSpec],
        urgent_orders: Optional[List[Order]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.scenario_id = scenario_id
        self.seed = seed
        self.dataset_name = dataset_name
        self.customers_count = customers_count
        self.vehicles_count = vehicles_count
        self.simulation_duration_mins = simulation_duration_mins
        self.step_size_mins = step_size_mins
        self._base_fleet = base_fleet
        self._base_road = base_road
        self.node_id_map = dict(node_id_map)
        self.disruptions = disruptions
        self.urgent_orders = urgent_orders or []
        self.meta = meta or {}

    def get_fleet_copy(self) -> FleetState:
        """Returns a pristine deep copy of the fleet for an algorithm run."""
        return self._base_fleet.model_copy(deep=True)

    def get_road_copy(self) -> RoadNetwork:
        """Returns a pristine deep copy of the road network for an algorithm run."""
        return copy.deepcopy(self._base_road)

    def get_orders_list(self) -> List[Order]:
        """Returns all initial orders."""
        return list(self._base_fleet.active_orders.values())

    def get_breakdown_spec(self) -> Optional[DisruptionSpec]:
        """Finds primary vehicle breakdown event if present."""
        for d in self.disruptions:
            if d.event_type == "BREAKDOWN":
                return d
        return None

    def get_connectivity_spec(self) -> Optional[DisruptionSpec]:
        """Finds primary connectivity loss event if present."""
        for d in self.disruptions:
            if d.event_type == "CONNECTIVITY_LOSS":
                return d
        return None


def generate_benchmark_scenario(
    seed: int = 42,
    dataset_name: str = "C101",
    customers_count: int = 25,
    vehicles_count: int = 5,
    simulation_duration_mins: float = 1200.0,
    step_size_mins: float = 2.0,
    base_disruption_time: float = 120.0,
) -> BenchmarkScenario:
    """
    Generates a reproducible, seed-controlled benchmark scenario.
    The seed pseudorandomly controls:
      - Breakdown timing (e.g. 90m to 150m) and target vehicle ID
      - Outage timing
      - Traffic congestion edge selection and intensity
      - Dynamic urgent order spatial offsets
    Every algorithm receiving this scenario object encounters the exact same conditions.
    """
    rng = np.random.default_rng(seed)

    # 1. Load baseline problem instance
    fleet, road, meta = load_solomon_benchmark(
        dataset_name, max_customers=customers_count, vehicle_count=vehicles_count
    )
    orders_list = list(fleet.active_orders.values())
    node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders_list)}

    # 2. Pseudorandomly select breakdown vehicle and timing from seed
    vehicle_ids = list(fleet.vehicles.keys())
    # Choose among vehicles with orders or first vehicle if unassigned
    veh_idx = int(rng.integers(0, min(3, len(vehicle_ids))))
    breakdown_veh_id = vehicle_ids[veh_idx]
    
    # Jitter disruption time by +/- 30 mins based on seed
    time_jitter = float(rng.uniform(-25.0, 25.0))
    breakdown_time = max(45.0, round(base_disruption_time + time_jitter, 1))
    outage_time = breakdown_time  # simultaneous cloud loss

    disruptions: List[DisruptionSpec] = []

    # Breakdown event
    disruptions.append(
        DisruptionSpec(
            event_id=f"DISR_BRK_{breakdown_veh_id}_s{seed}",
            event_type="BREAKDOWN",
            timestamp_mins=breakdown_time,
            payload={"vehicle_id": breakdown_veh_id},
            description=f"Mechanical failure on {breakdown_veh_id}",
        )
    )

    # Connectivity loss event
    disruptions.append(
        DisruptionSpec(
            event_id=f"DISR_OUTAGE_s{seed}",
            event_type="CONNECTIVITY_LOSS",
            timestamp_mins=outage_time,
            payload={"target_mode": ConnectivityState.MESH_MODE},
            description="Cellular and cloud connectivity lost across region",
        )
    )

    # Traffic congestion spikes (2-3 random edges)
    edge_list = list(road.graph.edges())
    if edge_list:
        num_spikes = int(rng.integers(2, 4))
        chosen_edges_idx = rng.choice(len(edge_list), size=min(num_spikes, len(edge_list)), replace=False)
        for idx in chosen_edges_idx:
            u, v = edge_list[idx]
            severity = rng.choice([TrafficLevel.HEAVY, TrafficLevel.SEVERE])
            disruptions.append(
                DisruptionSpec(
                    event_id=f"DISR_TRAFFIC_{u}_{v}_s{seed}",
                    event_type="TRAFFIC_SPIKE",
                    timestamp_mins=max(30.0, breakdown_time - 30.0),
                    payload={"u": u, "v": v, "traffic_level": severity.value},
                    description=f"Congestion spike on edge ({u}, {v})",
                )
            )

    # Dynamic urgent express orders (2 urgent orders released near disruption time)
    depot_coord = meta.get("depot_coord", (50.0, 50.0))
    urgent_orders = []
    for i in range(1, 3):
        uo_id = f"URG_s{seed}_{i:02d}"
        angle = float(rng.uniform(0, 2 * math.pi))
        radius = float(rng.uniform(8.0, 22.0))
        dest = (round(depot_coord[0] + radius * math.cos(angle), 2), round(depot_coord[1] + radius * math.sin(angle), 2))
        uo = Order(
            order_id=uo_id,
            pickup_location=depot_coord,
            destination=dest,
            demand_weight=round(float(rng.uniform(5.0, 15.0)), 1),
            priority=5,
            earliest_delivery=breakdown_time,
            latest_delivery=breakdown_time + 150.0,
            service_time=15.0,
            release_time=breakdown_time,
            status=OrderStatus.PENDING,
        )
        urgent_orders.append(uo)
        # Register in road network
        new_node_idx = customers_count + i
        road.add_node(new_node_idx, x=dest[0], y=dest[1], demand=uo.demand_weight, ready_time=uo.earliest_delivery, due_date=uo.latest_delivery)
        node_id_map[uo_id] = new_node_idx
        fleet.active_orders[uo_id] = uo

    scenario_id = f"scenario_{dataset_name}_c{customers_count}_v{vehicles_count}_s{seed}"

    return BenchmarkScenario(
        scenario_id=scenario_id,
        seed=seed,
        dataset_name=dataset_name,
        customers_count=customers_count,
        vehicles_count=vehicles_count,
        simulation_duration_mins=simulation_duration_mins,
        step_size_mins=step_size_mins,
        base_fleet=fleet,
        base_road=road,
        node_id_map=node_id_map,
        disruptions=disruptions,
        urgent_orders=urgent_orders,
        meta=meta,
    )


def generate_disruption_scenarios(
    seed: int = 42,
    dataset_name: str = "C101",
    customers_count: int = 20,
    vehicles_count: int = 5,
) -> Dict[str, BenchmarkScenario]:
    """
    Generates Scenarios A through H covering distinct failure modalities:
      - Scenario A: Single truck breakdown
      - Scenario B: Two truck breakdowns
      - Scenario C: Severe traffic congestion
      - Scenario D: Cloud outage
      - Scenario E: Cloud outage + truck breakdown
      - Scenario F: Cloud outage + breakdown + traffic congestion
      - Scenario G: Sudden demand burst
      - Scenario H: Combined disruption
    """
    scenarios = {}
    names = [
        ("A", "Single truck breakdown"),
        ("B", "Two truck breakdowns"),
        ("C", "Traffic congestion"),
        ("D", "Cloud outage"),
        ("E", "Cloud outage + truck breakdown"),
        ("F", "Cloud outage + breakdown + traffic"),
        ("G", "Sudden demand burst"),
        ("H", "Combined disruption"),
    ]

    for code, desc in names:
        fleet, road, meta = load_solomon_benchmark(
            dataset_name, max_customers=customers_count, vehicle_count=vehicles_count
        )
        orders_list = list(fleet.active_orders.values())
        node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders_list)}
        vehs = list(fleet.vehicles.keys())
        disruptions = []

        if code in ("A", "E", "F", "H"):
            disruptions.append(DisruptionSpec(
                event_id=f"DISR_BRK1_{code}",
                event_type="BREAKDOWN",
                timestamp_mins=90.0,
                payload={"vehicle_id": vehs[0]},
                description=f"Breakdown on {vehs[0]}",
            ))

        if code in ("B", "H") and len(vehs) > 1:
            disruptions.append(DisruptionSpec(
                event_id=f"DISR_BRK2_{code}",
                event_type="BREAKDOWN",
                timestamp_mins=140.0,
                payload={"vehicle_id": vehs[1]},
                description=f"Breakdown on {vehs[1]}",
            ))

        if code in ("D", "E", "F", "H"):
            disruptions.append(DisruptionSpec(
                event_id=f"DISR_OUTAGE_{code}",
                event_type="CONNECTIVITY_LOSS",
                timestamp_mins=90.0,
                payload={"target_mode": ConnectivityState.MESH_MODE},
                description="Cloud outage",
            ))

        if code in ("C", "F", "H"):
            edges = list(road.graph.edges())
            for idx in range(min(3, len(edges))):
                u, v = edges[idx]
                disruptions.append(DisruptionSpec(
                    event_id=f"DISR_TRAFFIC_{u}_{v}_{code}",
                    event_type="TRAFFIC_SPIKE",
                    timestamp_mins=60.0,
                    payload={"u": u, "v": v, "traffic_level": TrafficLevel.SEVERE.value},
                    description=f"Traffic blockage on ({u}, {v})",
                ))

        urgent_orders = []
        if code in ("G", "H"):
            depot_coord = meta.get("depot_coord", (50.0, 50.0))
            for i in range(1, 5):
                uo_id = f"URG_{code}_{i}"
                dest = (depot_coord[0] + 10.0 * math.cos(i * 1.5), depot_coord[1] + 10.0 * math.sin(i * 1.5))
                uo = Order(
                    order_id=uo_id,
                    pickup_location=depot_coord,
                    destination=dest,
                    demand_weight=10.0,
                    earliest_delivery=60.0,
                    latest_delivery=240.0,
                    release_time=60.0,
                    status=OrderStatus.PENDING,
                )
                urgent_orders.append(uo)
                nid = customers_count + i
                road.add_node(nid, x=dest[0], y=dest[1], demand=10.0, ready_time=60.0, due_date=240.0)
                node_id_map[uo_id] = nid
                fleet.active_orders[uo_id] = uo

        scenarios[code] = BenchmarkScenario(
            scenario_id=f"Scenario_{code}_{desc.replace(' ', '_')}",
            seed=seed,
            dataset_name=dataset_name,
            customers_count=customers_count,
            vehicles_count=vehicles_count,
            simulation_duration_mins=1200.0,
            step_size_mins=2.0,
            base_fleet=fleet,
            base_road=road,
            node_id_map=node_id_map,
            disruptions=disruptions,
            urgent_orders=urgent_orders,
            meta=meta,
        )

    return scenarios

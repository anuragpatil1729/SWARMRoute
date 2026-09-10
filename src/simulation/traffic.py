from __future__ import annotations
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from src.models.road import Road, RoadNetwork, RoadStatus, TrafficLevel


class TrafficIncident(BaseModel):
    """Represents a temporary disruption on a road segment or geographic corridor."""
    incident_id: str
    incident_type: str  # "ACCIDENT", "CONGESTION_SPIKE", "ROAD_CLOSURE"
    edge: Tuple[Union[int, str], Union[int, str]]
    severity: TrafficLevel
    start_time_mins: float
    end_time_mins: float
    is_active: bool = True


class TrafficSimulator:
    """
    Configurable, deterministic Traffic Simulation Engine.
    Models:
      - Diurnal baseline traffic cycle across the 24-hour day.
      - Dynamic speed reductions and travel time inflation.
      - Stochastic disruptive incidents: accidents, congestion spikes, road closures.
    """

    DEFAULT_HOURLY_BASE_CYCLE: Dict[int, TrafficLevel] = {
        0: TrafficLevel.LIGHT,
        1: TrafficLevel.LIGHT,
        2: TrafficLevel.LIGHT,
        3: TrafficLevel.LIGHT,
        4: TrafficLevel.LIGHT,
        5: TrafficLevel.LIGHT,
        6: TrafficLevel.LIGHT,
        7: TrafficLevel.NORMAL,
        8: TrafficLevel.HEAVY,       # Morning rush peak
        9: TrafficLevel.SEVERE,
        10: TrafficLevel.MODERATE,
        11: TrafficLevel.LIGHT,
        12: TrafficLevel.NORMAL,
        13: TrafficLevel.NORMAL,
        14: TrafficLevel.NORMAL,
        15: TrafficLevel.NORMAL,
        16: TrafficLevel.MODERATE,
        17: TrafficLevel.HEAVY,      # Evening rush peak
        18: TrafficLevel.SEVERE,
        19: TrafficLevel.MODERATE,
        20: TrafficLevel.LIGHT,
        21: TrafficLevel.LIGHT,
        22: TrafficLevel.LIGHT,
        23: TrafficLevel.LIGHT,
    }

    def __init__(
        self,
        hourly_schedule: Optional[Dict[int, TrafficLevel]] = None,
        accident_probability: float = 0.05,
        spike_probability: float = 0.10,
        seed: Optional[int] = 42,
    ) -> None:
        self.hourly_schedule = hourly_schedule or self.DEFAULT_HOURLY_BASE_CYCLE.copy()
        self.accident_probability = accident_probability
        self.spike_probability = spike_probability
        self.rng = random.Random(seed)
        self.active_incidents: List[TrafficIncident] = []
        self.incident_counter = 0

    def trigger_accident(
        self,
        edge: Tuple[Union[int, str], Union[int, str]],
        current_time_mins: float,
        duration_mins: float = 45.0,
        severity: TrafficLevel = TrafficLevel.SEVERE,
    ) -> TrafficIncident:
        self.incident_counter += 1
        incident = TrafficIncident(
            incident_id=f"INC_ACC_{self.incident_counter:03d}",
            incident_type="ACCIDENT",
            edge=edge,
            severity=severity,
            start_time_mins=current_time_mins,
            end_time_mins=current_time_mins + duration_mins,
        )
        self.active_incidents.append(incident)
        return incident

    def trigger_road_closure(
        self,
        edge: Tuple[Union[int, str], Union[int, str]],
        current_time_mins: float,
        duration_mins: float = 120.0,
    ) -> TrafficIncident:
        self.incident_counter += 1
        incident = TrafficIncident(
            incident_id=f"INC_CLS_{self.incident_counter:03d}",
            incident_type="ROAD_CLOSURE",
            edge=edge,
            severity=TrafficLevel.BLOCKED,
            start_time_mins=current_time_mins,
            end_time_mins=current_time_mins + duration_mins,
        )
        self.active_incidents.append(incident)
        return incident

    def trigger_congestion_spike(
        self,
        edge: Tuple[Union[int, str], Union[int, str]],
        current_time_mins: float,
        duration_mins: float = 60.0,
    ) -> TrafficIncident:
        self.incident_counter += 1
        incident = TrafficIncident(
            incident_id=f"INC_SPK_{self.incident_counter:03d}",
            incident_type="CONGESTION_SPIKE",
            edge=edge,
            severity=TrafficLevel.HEAVY,
            start_time_mins=current_time_mins,
            end_time_mins=current_time_mins + duration_mins,
        )
        self.active_incidents.append(incident)
        return incident

    def get_base_traffic_for_time(self, current_time_mins: float) -> TrafficLevel:
        hour = int((current_time_mins / 60.0) % 24)
        return self.hourly_schedule.get(hour, TrafficLevel.NORMAL)

    def get_edge_traffic(
        self,
        edge: Tuple[Union[int, str], Union[int, str]],
        current_time_mins: float,
    ) -> Tuple[TrafficLevel, Optional[TrafficIncident]]:
        """Returns effective traffic level on this edge, considering active incidents."""
        base_level = self.get_base_traffic_for_time(current_time_mins)
        active_inc = None

        for inc in self.active_incidents:
            if inc.is_active and (inc.start_time_mins <= current_time_mins <= inc.end_time_mins):
                if inc.edge == edge or inc.edge == (edge[1], edge[0]):
                    active_inc = inc
                    return inc.severity, active_inc

        return base_level, None

    def step(self, current_time_mins: float) -> List[TrafficIncident]:
        """Advances simulator time, prunes expired incidents, and returns active ones."""
        still_active = []
        for inc in self.active_incidents:
            if current_time_mins > inc.end_time_mins:
                inc.is_active = False
            else:
                still_active.append(inc)
        self.active_incidents = still_active
        return self.active_incidents

    def update_road_network(
        self, road_network: RoadNetwork, current_time_mins: float
    ) -> Dict[Tuple[Any, Any], TrafficLevel]:
        """
        Applies current traffic conditions across all graph edges in the road network.
        Updates speeds, road statuses, and edge travel times.
        """
        self.step(current_time_mins)
        active_state: Dict[Tuple[Any, Any], TrafficLevel] = {}

        for u, v in road_network.graph.edges():
            level, inc = self.get_edge_traffic((u, v), current_time_mins)
            active_state[(u, v)] = level

            edge_data = road_network.graph[u][v]
            speed_limit = edge_data.get("speed_limit", 50.0)
            road_obj: Optional[Road] = edge_data.get("road")

            if road_obj:
                road_obj.update_traffic(level)
                edge_data["speed"] = road_obj.current_speed
                edge_data["traffic"] = road_obj.traffic_level
                edge_data["status"] = road_obj.status
            else:
                current_spd = max(1.0, speed_limit * level.speed_multiplier)
                edge_data["speed"] = current_spd
                edge_data["traffic"] = level
                edge_data["status"] = RoadStatus.CLOSED if level == TrafficLevel.BLOCKED else RoadStatus.OPEN

        return active_state

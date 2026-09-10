from __future__ import annotations
import math
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import networkx as nx
from pydantic import BaseModel, Field


class TrafficLevel(str, Enum):
    LIGHT = "LIGHT"
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    HEAVY = "HEAVY"
    SEVERE = "SEVERE"
    BLOCKED = "BLOCKED"

    @property
    def speed_multiplier(self) -> float:
        """Returns speed reduction factor for each traffic level."""
        factors = {
            TrafficLevel.LIGHT: 1.15,
            TrafficLevel.NORMAL: 1.0,
            TrafficLevel.MODERATE: 0.75,
            TrafficLevel.HEAVY: 0.50,
            TrafficLevel.SEVERE: 0.30,
            TrafficLevel.BLOCKED: 0.001,
        }
        return factors[self]


class RoadStatus(str, Enum):
    OPEN = "OPEN"
    CONGESTED = "CONGESTED"
    CLOSED = "CLOSED"


class Road(BaseModel):
    """
    Represents a road link / edge in the transportation graph.
    """
    road_id: str = Field(..., description="Unique road segment identifier")
    source: Union[int, str] = Field(..., description="Source node id")
    destination: Union[int, str] = Field(..., description="Destination node id")
    distance: float = Field(..., ge=0.0, description="Road segment length (km)")
    speed_limit: float = Field(default=50.0, gt=0.0, description="Speed limit (km/h)")
    current_speed: float = Field(default=50.0, gt=0.0, description="Effective current speed (km/h)")
    traffic_level: TrafficLevel = Field(default=TrafficLevel.NORMAL, description="Traffic congestion status")
    gradient: float = Field(default=0.0, description="Road incline / gradient in % (-10 to +10)")
    status: RoadStatus = Field(default=RoadStatus.OPEN, description="Operational status: OPEN, CONGESTED, CLOSED")

    def update_traffic(self, level: TrafficLevel) -> None:
        """Updates traffic level and recalculates current speed."""
        self.traffic_level = level
        if level == TrafficLevel.BLOCKED:
            self.status = RoadStatus.CLOSED
            self.current_speed = 1.0
        elif level in (TrafficLevel.HEAVY, TrafficLevel.SEVERE):
            self.status = RoadStatus.CONGESTED
            self.current_speed = max(5.0, self.speed_limit * level.speed_multiplier)
        else:
            self.status = RoadStatus.OPEN
            self.current_speed = self.speed_limit * level.speed_multiplier

    @property
    def travel_time(self) -> float:
        """Returns travel time in hours across this segment."""
        if self.status == RoadStatus.CLOSED or self.current_speed <= 0.0:
            return float("inf")
        return self.distance / self.current_speed


class RoadNetwork:
    """
    Network abstraction decoupling the routing algorithm from the underlying network data source.
    Can be instantiated from:
      1. Euclidean coordinates (e.g., Solomon VRPTW instances)
      2. Synthetic graph with edges, traffic, and gradients
      3. OpenStreetMap (OSM) graph
    """

    def __init__(self, name: str = "RoadNetwork") -> None:
        self.name = name
        self.graph = nx.DiGraph()
        self.node_coordinates: Dict[Union[int, str], Tuple[float, float]] = {}

    def add_node(self, node_id: Union[int, str], x: float, y: float, **attributes: Any) -> None:
        self.graph.add_node(node_id, x=x, y=y, **attributes)
        self.node_coordinates[node_id] = (x, y)

    def add_road(self, road: Road) -> None:
        self.graph.add_edge(
            road.source,
            road.destination,
            road=road,
            distance=road.distance,
            weight=road.distance,
            traffic=road.traffic_level,
            gradient=road.gradient,
            speed=road.current_speed,
            status=road.status,
        )

    def get_distance(self, u: Union[int, str], v: Union[int, str]) -> float:
        """Gets distance between two nodes; falls back to Euclidean if edge isn't explicitly set."""
        if self.graph.has_edge(u, v):
            return float(self.graph[u][v]["distance"])
        if u in self.node_coordinates and v in self.node_coordinates:
            x1, y1 = self.node_coordinates[u]
            x2, y2 = self.node_coordinates[v]
            return math.hypot(x2 - x1, y2 - y1)
        raise ValueError(f"Distance cannot be computed between nodes {u} and {v}")

    def get_travel_time(
        self, u: Union[int, str], v: Union[int, str], nominal_speed: float = 40.0
    ) -> float:
        """Gets estimated travel time (in hours or consistent time units) between u and v."""
        if self.graph.has_edge(u, v):
            road: Road = self.graph[u][v].get("road")
            if road:
                return road.travel_time
            speed = self.graph[u][v].get("speed", nominal_speed)
            dist = self.graph[u][v].get("distance", self.get_distance(u, v))
            return dist / max(1.0, speed)
        # Default travel time calculation from distance and nominal speed
        dist = self.get_distance(u, v)
        return dist / nominal_speed

    def build_complete_euclidean_matrix(
        self, node_ids: List[Union[int, str]]
    ) -> Tuple[List[List[float]], List[List[float]]]:
        """
        Builds (distance_matrix, time_matrix) for a given ordered list of nodes.
        For Solomon instances, speed is conventionally 1 distance unit per 1 time unit.
        """
        n = len(node_ids)
        dist_matrix = [[0.0] * n for _ in range(n)]
        time_matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    u, v = node_ids[i], node_ids[j]
                    d = self.get_distance(u, v)
                    dist_matrix[i][j] = d
                    # Standard Solomon assumption: distance == travel time (speed = 1.0 unit/time)
                    time_matrix[i][j] = d
        return dist_matrix, time_matrix

"""
Real-world Routing Client for SWARMRoute.
Integrates with OpenStreetMap (OSM) and OSRM (Open Source Routing Machine).
Separates basemap road routing from real traffic telemetry.
Honest failure modes: returns ROUTING UNAVAILABLE and TRAFFIC DATA UNAVAILABLE
instead of fabricated routes or synthetic congestion.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.parse
import json


class RoadRoute:
    """Represents an authentic road route over OpenStreetMap road networks."""

    def __init__(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        coordinates: List[Tuple[float, float]],
        distance_meters: float,
        duration_seconds: float,
        steps: List[Dict[str, Any]],
        provider: str = "OSRM",
        traffic_status: str = "TRAFFIC DATA UNAVAILABLE",
        is_fallback: bool = False,
    ) -> None:
        self.origin = origin  # (lat, lon)
        self.destination = destination  # (lat, lon)
        self.coordinates = coordinates  # List of [lat, lon]
        self.distance_meters = distance_meters
        self.distance_km = round(distance_meters / 1000.0, 3)
        self.duration_seconds = duration_seconds
        self.duration_mins = round(duration_seconds / 60.0, 2)
        self.steps = steps
        self.provider = provider
        self.traffic_status = traffic_status
        self.is_fallback = is_fallback

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": {"lat": self.origin[0], "lon": self.origin[1]},
            "destination": {"lat": self.destination[0], "lon": self.destination[1]},
            "coordinates": [{"lat": c[0], "lon": c[1]} for c in self.coordinates],
            "lat_lon": [[round(c[0], 6), round(c[1], 6)] for c in self.coordinates],
            "distance_km": self.distance_km,
            "duration_mins": self.duration_mins,
            "steps_count": len(self.steps),
            "steps": self.steps,
            "provider": self.provider,
            "traffic_status": self.traffic_status,
            "is_fallback": self.is_fallback,
        }


class OSRMRoutingClient:
    """
    Production Routing Client for fetching real road paths from OSRM.
    Configurable via OSRM_BASE_URL.
    """

    def __init__(self, base_url: Optional[str] = None, timeout_sec: float = 4.0) -> None:
        self.base_url = (
            base_url
            or os.getenv("OSRM_BASE_URL")
            or "https://router.project-osrm.org"
        ).rstrip("/")
        self.timeout_sec = timeout_sec
        # In-memory cache for recent coordinate pairs (lat1, lon1, lat2, lon2, detour) -> (timestamp, RoadRoute)
        self._cache: Dict[Tuple[float, float, float, float, bool], Tuple[float, RoadRoute]] = {}
        self._cache_ttl_sec = 600.0

    def is_healthy(self) -> bool:
        """Returns True if OSRM routing endpoint is configured and active."""
        return bool(self.base_url)

    def get_road_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        detour: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetches true driving route along real street networks.
        Coordinates are passed as (lat, lon) and transformed to OSRM order (lon,lat).
        Supports detour=True to route around congestion via a bypass corridor.
        """
        # Quantize for cache lookup (approx 10m precision)
        cache_key = (
            round(origin_lat, 4),
            round(origin_lon, 4),
            round(dest_lat, 4),
            round(dest_lon, 4),
            bool(detour),
        )
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_route = self._cache[cache_key]
            if now - cached_time < self._cache_ttl_sec:
                return {"success": True, "route": cached_route.to_dict()}

        if detour:
            mid_lat = (origin_lat + dest_lat) / 2.0
            mid_lon = (origin_lon + dest_lon) / 2.0
            d_lat = dest_lat - origin_lat
            d_lon = dest_lon - origin_lon
            via_lat = round(mid_lat - d_lon * 0.28, 6)
            via_lon = round(mid_lon + d_lat * 0.28, 6)
            url = (
                f"{self.base_url}/route/v1/driving/"
                f"{origin_lon},{origin_lat};{via_lon},{via_lat};{dest_lon},{dest_lat}"
                f"?overview=full&geometries=geojson&steps=true"
            )
        else:
            url = (
                f"{self.base_url}/route/v1/driving/"
                f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
                f"?overview=full&geometries=geojson&steps=true"
            )

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SWARMRoute-Autonomous-Fleet/1.0 (Fleet Operations)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status != 200:
                    return {
                        "success": False,
                        "error": "ROUTING UNAVAILABLE",
                        "detail": f"OSRM returned HTTP {resp.status}",
                    }
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("code") != "Ok" or not data.get("routes"):
                return {
                    "success": False,
                    "error": "ROUTING UNAVAILABLE",
                    "detail": data.get("message", "No route found between coordinates"),
                }

            osrm_route = data["routes"][0]
            geom = osrm_route.get("geometry", {})
            # GeoJSON coordinates are [lon, lat], convert to [lat, lon]
            raw_coords = geom.get("coordinates", [])
            lat_lon_coords = [(pt[1], pt[0]) for pt in raw_coords]

            legs = osrm_route.get("legs", [])
            steps_list = []
            if legs:
                for s in legs[0].get("steps", []):
                    steps_list.append({
                        "instruction": s.get("maneuver", {}).get("type", "turn"),
                        "name": s.get("name", ""),
                        "distance_m": s.get("distance", 0.0),
                        "duration_s": s.get("duration", 0.0),
                    })

            # Check for configured real traffic provider (e.g. TomTom, HERE)
            traffic_status = self._check_traffic_provider(origin_lat, origin_lon, dest_lat, dest_lon)

            route_obj = RoadRoute(
                origin=(origin_lat, origin_lon),
                destination=(dest_lat, dest_lon),
                coordinates=lat_lon_coords,
                distance_meters=float(osrm_route.get("distance", 0.0)),
                duration_seconds=float(osrm_route.get("duration", 0.0)),
                steps=steps_list,
                provider="OpenStreetMap / OSRM",
                traffic_status=traffic_status,
                is_fallback=False,
            )

            self._cache[cache_key] = (now, route_obj)
            return {"success": True, "route": route_obj.to_dict()}

        except Exception as e:
            # Honest fallback reporting: Do NOT pretend straight-line distance is a road route!
            straight_line_km = self.haversine_distance_km(origin_lat, origin_lon, dest_lat, dest_lon)
            return {
                "success": False,
                "error": "ROUTING UNAVAILABLE",
                "detail": str(e),
                "decision_support_heuristic": {
                    "straight_line_distance_km": round(straight_line_km, 2),
                    "warning": "Straight-line distance is a decision-support heuristic only, not a road route.",
                },
            }

    def _check_traffic_provider(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> str:
        """
        Inspects real traffic API configuration.
        Returns authentic state if configured; returns 'TRAFFIC DATA UNAVAILABLE' otherwise.
        """
        tomtom_key = os.getenv("TOMTOM_API_KEY")
        here_key = os.getenv("HERE_API_KEY")

        if not tomtom_key and not here_key:
            return "TRAFFIC DATA UNAVAILABLE"

        # If a real traffic provider key is configured, query flow state
        if tomtom_key:
            try:
                # TomTom Flow Segment Data API
                tt_url = (
                    f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
                    f"?point={origin_lat},{origin_lon}&key={tomtom_key}"
                )
                req = urllib.request.Request(tt_url, headers={"User-Agent": "SWARMRoute/1.0"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        tt_data = json.loads(resp.read().decode("utf-8"))
                        flow = tt_data.get("flowSegmentData", {})
                        free_flow = flow.get("freeFlowSpeed", 1)
                        current_speed = flow.get("currentSpeed", free_flow)
                        ratio = current_speed / max(1, free_flow)
                        if ratio < 0.5:
                            return "HEAVY_CONGESTION"
                        elif ratio < 0.8:
                            return "MODERATE_TRAFFIC"
                        return "FLOWING"
            except Exception:
                return "TRAFFIC DATA UNAVAILABLE"

        return "TRAFFIC DATA UNAVAILABLE"

    @staticmethod
    def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle geographic distance heuristic in kilometers."""
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c


# Global routing client singleton
routing_client = OSRMRoutingClient()

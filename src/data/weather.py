"""
weather.py — standalone weather data provider for SWARMRoute.

This is a NEW, self-contained module. It does not import from or modify
any existing file in src/simulation, src/agents, or src/optimization.
Drop it in as `src/data/weather.py` and wire it in yourself at the two
integration points described in INTEGRATION.md — that keeps the blast
radius to "one new file" until you're ready to touch the simulator.

Two providers are included:
  - MockWeatherProvider: deterministic/seeded synthetic weather, good for
    tests and for demoing without any network dependency.
  - OpenMeteoWeatherProvider: real weather via the free Open-Meteo API
    (no API key required). Swap in a different provider if you'd rather
    use a paid service — the interface (`WeatherProvider`) is the only
    contract the rest of the code needs to depend on.

Design goal: whatever consumes this (PPO observation builder, event
system, dashboard) should only ever touch `WeatherSnapshot` and the
`WeatherProvider.get_current(lat, lon)` / `.get_severity()` methods, so
swapping providers later never requires touching the caller again.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

try:
    import requests  # only needed for OpenMeteoWeatherProvider
except ImportError:  # pragma: no cover
    requests = None


class WeatherCondition(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    FOG = "fog"
    STORM = "storm"


@dataclass(frozen=True)
class WeatherSnapshot:
    """One point-in-time weather reading for a location."""

    condition: WeatherCondition
    temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float
    visibility_km: float
    timestamp: datetime

    @property
    def severity(self) -> float:
        """
        Normalized 0.0-1.0 severity score, meant to be dropped straight
        into a feature vector (e.g. as a replacement/addition to one of
        the PPO agent's 25 observation dims).

        0.0 = ideal driving conditions, 1.0 = severe/hazardous.
        """
        score = 0.0
        score += {
            WeatherCondition.CLEAR: 0.0,
            WeatherCondition.CLOUDY: 0.1,
            WeatherCondition.RAIN: 0.4,
            WeatherCondition.HEAVY_RAIN: 0.7,
            WeatherCondition.FOG: 0.5,
            WeatherCondition.STORM: 0.9,
        }[self.condition]
        # Visibility below 5km and wind above 40kmh push severity up further.
        if self.visibility_km < 5:
            score += (5 - self.visibility_km) / 10
        if self.wind_speed_kmh > 40:
            score += min((self.wind_speed_kmh - 40) / 100, 0.2)
        return max(0.0, min(1.0, score))

    @property
    def speed_multiplier(self) -> float:
        """
        Suggested multiplier on nominal travel speed for use in the
        discrete-event simulator (src/simulation/environment.py) or the
        travel-time predictor — 1.0 = no slowdown, lower = slower.
        Kept separate from `severity` so the two can be tuned independently.
        """
        return max(0.4, 1.0 - 0.5 * self.severity)


class WeatherProvider(ABC):
    @abstractmethod
    def get_current(self, lat: float, lon: float) -> WeatherSnapshot:
        ...


class MockWeatherProvider(WeatherProvider):
    """
    Deterministic-if-seeded synthetic weather generator. Use this for
    unit tests, CI, and the PPO training loop where you want reproducible
    episodes rather than live network calls.
    """

    def __init__(self, seed: Optional[int] = None, bias: Optional[WeatherCondition] = None):
        self._rng = random.Random(seed)
        self._bias = bias

    def get_current(self, lat: float, lon: float) -> WeatherSnapshot:
        condition = self._bias or self._rng.choice(list(WeatherCondition))
        return WeatherSnapshot(
            condition=condition,
            temperature_c=round(self._rng.uniform(10, 35), 1),
            precipitation_mm=round(self._rng.uniform(0, 20), 1)
            if condition in (WeatherCondition.RAIN, WeatherCondition.HEAVY_RAIN, WeatherCondition.STORM)
            else 0.0,
            wind_speed_kmh=round(self._rng.uniform(0, 60), 1),
            visibility_km=round(self._rng.uniform(1, 15), 1),
            timestamp=datetime.now(timezone.utc),
        )


class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Real weather via https://open-meteo.com — free, no API key required.
    Falls back to raising if the `requests` package isn't installed;
    add `requests` to requirements.txt to enable this provider.
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def get_current(self, lat: float, lon: float) -> WeatherSnapshot:
        if requests is None:
            raise RuntimeError(
                "OpenMeteoWeatherProvider requires the 'requests' package. "
                "Add it to requirements.txt, or use MockWeatherProvider instead."
            )
        resp = requests.get(
            self.BASE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,wind_speed_10m,visibility,weather_code",
            },
            timeout=5,
        )
        resp.raise_for_status()
        current = resp.json()["current"]
        return WeatherSnapshot(
            condition=self._map_weather_code(current.get("weather_code", 0)),
            temperature_c=current.get("temperature_2m", 20.0),
            precipitation_mm=current.get("precipitation", 0.0),
            wind_speed_kmh=current.get("wind_speed_10m", 0.0),
            visibility_km=(current.get("visibility", 10000) or 10000) / 1000.0,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _map_weather_code(code: int) -> WeatherCondition:
        # WMO weather codes, simplified per Open-Meteo's docs.
        if code == 0:
            return WeatherCondition.CLEAR
        if code in (1, 2, 3):
            return WeatherCondition.CLOUDY
        if code in (45, 48):
            return WeatherCondition.FOG
        if code in (51, 53, 55, 61, 63, 80, 81):
            return WeatherCondition.RAIN
        if code in (65, 82, 66, 67):
            return WeatherCondition.HEAVY_RAIN
        if code in (95, 96, 99):
            return WeatherCondition.STORM
        return WeatherCondition.CLOUDY


def get_default_provider(use_live: bool = False, seed: Optional[int] = None) -> WeatherProvider:
    """Convenience factory — swap the default here once you decide which provider to standardize on."""
    if use_live:
        return OpenMeteoWeatherProvider()
    return MockWeatherProvider(seed=seed)

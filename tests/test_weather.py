import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.data.weather import (
    WeatherCondition,
    WeatherSnapshot,
    WeatherProvider,
    MockWeatherProvider,
    OpenMeteoWeatherProvider,
    get_default_provider,
)
from src.simulation.events import EventEngine, FleetEvent, EventType
from src.models.fleet_state import FleetState, ConnectivityState
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.simulation.environment import FleetSimulationEnvironment
from src.rl.environment import SWARMRLEnv


def test_mock_weather_provider_seed_determinism():
    p1 = MockWeatherProvider(seed=42)
    p2 = MockWeatherProvider(seed=42)
    s1 = p1.get_current(12.9716, 77.5946)
    s2 = p2.get_current(12.9716, 77.5946)
    assert s1.condition == s2.condition
    assert s1.temperature_c == s2.temperature_c
    assert s1.wind_speed_kmh == s2.wind_speed_kmh
    assert s1.visibility_km == s2.visibility_km
    assert s1.severity == s2.severity
    assert s1.speed_multiplier == s2.speed_multiplier


def test_mock_weather_provider_bias():
    provider = MockWeatherProvider(bias=WeatherCondition.STORM)
    snap = provider.get_current(0.0, 0.0)
    assert snap.condition == WeatherCondition.STORM
    assert snap.severity >= 0.9
    assert snap.speed_multiplier <= 0.55


def test_weather_snapshot_severity_and_speed_multiplier_bounds():
    # Ideal clear day
    snap_clear = WeatherSnapshot(
        condition=WeatherCondition.CLEAR,
        temperature_c=25.0,
        precipitation_mm=0.0,
        wind_speed_kmh=10.0,
        visibility_km=10.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert snap_clear.severity == 0.0
    assert snap_clear.speed_multiplier == 1.0

    # Extreme storm with low visibility and high winds
    snap_storm = WeatherSnapshot(
        condition=WeatherCondition.STORM,
        temperature_c=15.0,
        precipitation_mm=50.0,
        wind_speed_kmh=80.0,
        visibility_km=1.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert 0.9 <= snap_storm.severity <= 1.0
    assert 0.4 <= snap_storm.speed_multiplier <= 0.55


def test_open_meteo_code_mapping():
    assert OpenMeteoWeatherProvider._map_weather_code(0) == WeatherCondition.CLEAR
    assert OpenMeteoWeatherProvider._map_weather_code(2) == WeatherCondition.CLOUDY
    assert OpenMeteoWeatherProvider._map_weather_code(45) == WeatherCondition.FOG
    assert OpenMeteoWeatherProvider._map_weather_code(61) == WeatherCondition.RAIN
    assert OpenMeteoWeatherProvider._map_weather_code(65) == WeatherCondition.HEAVY_RAIN
    assert OpenMeteoWeatherProvider._map_weather_code(95) == WeatherCondition.STORM


def test_open_meteo_provider_mocked_request():
    provider = OpenMeteoWeatherProvider()
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "current": {
            "temperature_2m": 22.5,
            "precipitation": 5.0,
            "wind_speed_10m": 15.0,
            "visibility": 8000,
            "weather_code": 61,
        }
    }
    fake_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=fake_response) as mock_get:
        snap = provider.get_current(12.9716, 77.5946)
        assert snap.condition == WeatherCondition.RAIN
        assert snap.temperature_c == 22.5
        assert snap.precipitation_mm == 5.0
        assert snap.visibility_km == 8.0
        mock_get.assert_called_once()


def test_get_default_provider_factory():
    mock_prov = get_default_provider(use_live=False, seed=123)
    assert isinstance(mock_prov, MockWeatherProvider)

    live_prov = get_default_provider(use_live=True)
    assert isinstance(live_prov, OpenMeteoWeatherProvider)


def test_event_engine_weather_event():
    engine = EventEngine()
    fleet = FleetState(connectivity_state=ConnectivityState.CLOUD_MODE)
    snap = WeatherSnapshot(
        condition=WeatherCondition.HEAVY_RAIN,
        temperature_c=18.0,
        precipitation_mm=25.0,
        wind_speed_kmh=45.0,
        visibility_km=3.0,
        timestamp=datetime.now(timezone.utc),
    )
    ev = FleetEvent(
        event_id="EV_WEATHER_01",
        event_type=EventType.WEATHER,
        timestamp=15.0,
        payload={"snapshot": snap},
    )
    engine.schedule(ev)
    due = engine.pop_due_events(20.0)
    assert len(due) == 1
    engine.apply_event(due[0], fleet)
    assert fleet.weather_state == snap


def test_simulation_environment_weather_speed_slowdown():
    # Setup simple road network with 2 nodes
    from src.models.road import Road
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=100.0, y=0.0)
    road.add_road(Road(road_id="R0_1", source=0, destination=1, distance=100.0, speed_limit=60.0))


    v = Vehicle(
        vehicle_id="TRUCK_TEST",
        max_weight=100.0,
        current_location=(0.0, 0.0),
        average_speed=60.0,
        current_route=[0, 1],
        status=VehicleStatus.EN_ROUTE,
    )
    fleet = FleetState(vehicles={"TRUCK_TEST": v})
    storm_provider = MockWeatherProvider(bias=WeatherCondition.STORM)

    sim = FleetSimulationEnvironment(
        fleet_state=fleet,
        road_network=road,
        node_id_map={"D0": 0, "C1": 1},
        weather_provider=storm_provider,
        step_size_mins=10.0,
        seed=42,
    )

    # Schedule weather event at T=0
    snap = storm_provider.get_current(0.0, 0.0)
    sim.event_engine.schedule(
        FleetEvent(
            event_id="EV_STORM",
            event_type=EventType.WEATHER,
            timestamp=0.0,
            payload={"snapshot": snap},
        )
    )

    sim.step()
    # Speed should be reduced by storm speed multiplier (< 1.0)
    assert sim.current_weather is not None
    assert sim.fleet_state.vehicles["TRUCK_TEST"].current_speed_kmh < 60.0 * 1.15
    road_obj = sim.road_network.graph[0][1]["road"]
    traffic_mult = road_obj.traffic_level.speed_multiplier
    assert sim.fleet_state.vehicles["TRUCK_TEST"].current_speed_kmh == pytest.approx(
        60.0 * traffic_mult * snap.speed_multiplier, rel=1e-2
    )



def test_rl_environment_weather_observation_dimension_contract():
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs, info = env.reset(seed=42)

    # Ensure 25-dim contract is strictly preserved
    assert SWARMRLEnv.OBS_DIM == 25
    assert env.observation_space.shape == (25,)
    assert obs.shape == (25,)
    assert len(obs) == 25

    # Check env friction / traffic dim (obs[6]) is within physical bounds [0, 1]
    assert 0.0 <= obs[6] <= 1.0

    # Step through env and verify obs stays consistent
    obs2, reward, terminated, truncated, info2 = env.step(4)  # HOLD action
    assert obs2.shape == (25,)
    assert 0.0 <= obs2[6] <= 1.0

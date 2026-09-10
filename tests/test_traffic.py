import pytest
from src.models.road import RoadNetwork, Road, TrafficLevel, RoadStatus
from src.simulation.traffic import TrafficSimulator, TrafficIncident


def test_traffic_hourly_schedule():
    sim = TrafficSimulator(seed=42)
    # Hour 2 is LIGHT (early morning)
    assert sim.get_base_traffic_for_time(2 * 60.0) == TrafficLevel.LIGHT
    # Hour 8 is HEAVY (morning rush)
    assert sim.get_base_traffic_for_time(8 * 60.0) == TrafficLevel.HEAVY
    # Hour 18 is SEVERE (evening rush)
    assert sim.get_base_traffic_for_time(18 * 60.0) == TrafficLevel.SEVERE


def test_traffic_accident_and_road_closure():
    sim = TrafficSimulator(seed=42)
    edge = (1, 2)

    # Trigger accident from T=30 to T=75 mins
    inc = sim.trigger_accident(edge=edge, current_time_mins=30.0, duration_mins=45.0)
    assert inc.is_active is True

    # At T=40 mins, edge should report accident severity
    level, active_inc = sim.get_edge_traffic(edge, current_time_mins=40.0)
    assert level == TrafficLevel.SEVERE
    assert active_inc is not None

    # At T=90 mins, accident has expired
    sim.step(90.0)
    assert inc.is_active is False
    level_after, active_inc_after = sim.get_edge_traffic(edge, current_time_mins=90.0)
    assert level_after != TrafficLevel.SEVERE


def test_update_road_network_traffic():
    network = RoadNetwork()
    network.add_node(1, 0.0, 0.0)
    network.add_node(2, 10.0, 0.0)
    road = Road(
        road_id="R12",
        source=1,
        destination=2,
        distance=10.0,
        speed_limit=60.0,
        current_speed=60.0,
    )
    network.add_road(road)

    sim = TrafficSimulator(seed=42)
    # Apply morning rush hour (T=500 mins = 8:20 AM)
    sim.update_road_network(network, current_time_mins=500.0)
    assert road.traffic_level == TrafficLevel.HEAVY
    assert road.current_speed < 60.0

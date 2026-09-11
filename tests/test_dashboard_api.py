"""
Unit tests for SWARMRoute Dashboard API & Simulation Runner.
Verifies REST endpoints, state normalization, and real-time disruption handling.
"""
from fastapi.testclient import TestClient
from src.api.server import app
from src.api.simulation_runner import runner

client = TestClient(app)


def test_dashboard_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert "SWARMRoute" in data["service"]


def test_dashboard_api_state_schema():
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.json()

    # Schema verification per Requirement 25
    assert "simulation" in data
    assert "fleet" in data
    assert "vehicles" in data
    assert "orders" in data
    assert "map" in data
    assert "traffic" in data
    assert "network" in data
    assert "mesh" in data
    assert "incidents" in data
    assert "ppo" in data
    assert "sustainability" in data
    assert "performance" in data
    assert "events" in data
    assert "timeline" in data

    # Live vehicle attributes per Requirement 2
    assert len(data["vehicles"]) == data["fleet"]["size"]
    v0 = data["vehicles"][0]
    assert "id" in v0
    assert "status" in v0
    assert "x" in v0 and "y" in v0
    assert "current_load" in v0
    assert "fuel_level" in v0
    assert "co2_kg" in v0
    assert "speed_kmh" in v0
    assert "mesh_neighbors" in v0


def test_dashboard_api_simulation_step():
    t_before = runner.env.current_time_mins
    res = client.post("/api/simulation/step")
    assert res.status_code == 200
    data = res.json()
    assert data["simulation"]["time"] == t_before + runner.step_size_mins


def test_dashboard_api_disruptions():
    # 1. Break Vehicle
    res_brk = client.post("/api/disruption/break", json={"vehicle_id": "TRUCK_01"})
    assert res_brk.status_code == 200
    assert res_brk.json()["success"] is True

    state = client.get("/api/state").json()
    assert len(state["incidents"]) > 0
    assert state["incidents"][0]["vehicle_id"] == "TRUCK_01"

    # 2. Toggle Cloud
    res_cloud = client.post("/api/disruption/cloud")
    assert res_cloud.status_code == 200
    assert "mode" in res_cloud.json()

    # 3. Inject Traffic
    res_traffic = client.post("/api/disruption/traffic", json={"level": "SEVERE"})
    assert res_traffic.status_code == 200
    assert res_traffic.json()["success"] is True


def test_dashboard_api_benchmarks():
    res = client.get("/api/benchmarks")
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        data = res.json()
        assert isinstance(data, dict)

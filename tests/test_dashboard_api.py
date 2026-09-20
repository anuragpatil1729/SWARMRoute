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
    if len(data["vehicles"]) > 0:
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


def test_dashboard_api_ppo_stepping_and_recovery_regression():
    """Verify that stepping updates PPO history and breakdown recovers stranded orders."""
    # Reset simulation to clean state
    res_reset = client.post("/api/simulation/reset", json={"dataset": "C101", "customers": 20, "vehicles": 4, "seed": 42})
    assert res_reset.status_code == 200

    # Step simulation and verify PPO history is updated
    res_step = client.post("/api/simulation/step")
    assert res_step.status_code == 200
    state = res_step.json()
    if state["ppo"]["enabled"]:
        assert len(state["ppo"]["history"]) > 0
        assert "reward" in state["ppo"]["history"][-1]
        assert "action" in state["ppo"]["history"][-1]

    # Break an active vehicle with assigned orders and verify contract-net recovery reassigns stranded orders
    target_vid = next((v["id"] for v in state["vehicles"] if len(v.get("assigned_orders", [])) > 0), "TRUCK_02")
    res_brk = client.post("/api/disruption/break", json={"vehicle_id": target_vid})
    assert res_brk.status_code == 200
    brk_data = res_brk.json()
    assert brk_data["success"] is True

    # Check incident was recorded with recovery status
    incident = brk_data["incident"]
    assert incident["recovery_status"] in ("RECOVERED", "PARTIAL")
    if incident["recovery_status"] == "RECOVERED":
        assert incident["recovery_vehicle"] != target_vid
        assert len(incident["stranded_orders"]) > 0

    # Verify orders were actually transferred in simulation environment
    state_after = client.get("/api/state").json()
    broken_veh = next(v for v in state_after["vehicles"] if v["id"] == target_vid)
    assert broken_veh["status"] == "BROKEN_DOWN"
    assert len(broken_veh["assigned_orders"]) == 0
    assert state_after["performance"]["reassigned"] > 0


def test_dashboard_api_delivery_partners():
    """Verify delivery partners endpoint returns enriched Indian partner profiles."""
    res = client.get("/api/partners")
    assert res.status_code == 200
    data = res.json()
    assert "partners" in data
    assert isinstance(data["partners"], list)
    if len(data["partners"]) > 0:
        p0 = data["partners"][0]
        assert "id" in p0
        assert "name" in p0
        assert "vehicle_model" in p0
        assert "registration" in p0
        assert "hub" in p0
        assert "city" in p0
        assert p0["city"] in ("Maharashtra", "Bengaluru")
        assert "rating" in p0
        assert "remaining_capacity" in p0


def test_dashboard_api_task_allocation_and_completion():
    """Verify Admin allocating a task and Delivery Partner completing it."""
    # Reset simulation
    res_reset = client.post("/api/simulation/reset", json={"dataset": "C101", "customers": 20, "vehicles": 4, "seed": 42})
    assert res_reset.status_code == 200

    state = client.get("/api/state").json()
    orders = state["orders"]
    assert len(orders) > 0
    target_order_id = orders[0]["id"]

    # 1. Company Manager allocates task to TRUCK_02 (Amit Sharma)
    res_alloc = client.post("/api/task/allocate", json={"order_id": target_order_id, "vehicle_id": "TRUCK_02"})
    assert res_alloc.status_code == 200
    alloc_data = res_alloc.json()
    assert alloc_data["success"] is True
    assert alloc_data["vehicle_id"] == "TRUCK_02"
    assert alloc_data["order_id"] == target_order_id

    # Verify state reflects allocation
    state_alloc = client.get("/api/state").json()
    t2 = next(v for v in state_alloc["vehicles"] if v["id"] == "TRUCK_02")
    assert target_order_id in t2["assigned_orders"]

    ord_state = next(o for o in state_alloc["orders"] if o["id"] == target_order_id)
    assert ord_state["assigned_vehicle"] == "TRUCK_02"
    assert ord_state["status"] == "ASSIGNED"

    # 2. Delivery Partner marks delivery as complete
    res_comp = client.post("/api/task/complete", json={"order_id": target_order_id, "vehicle_id": "TRUCK_02"})
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["success"] is True

    # Verify state reflects delivery
    state_delivered = client.get("/api/state").json()
    ord_deliv = next(o for o in state_delivered["orders"] if o["id"] == target_order_id)
    assert ord_deliv["status"] == "DELIVERED"
    assert state_delivered["performance"]["delivered"] >= 1


def test_dashboard_api_task_allocation_validation_errors():
    """Verify capacity and breakdown guardrails during allocation."""
    # Break TRUCK_03
    client.post("/api/disruption/break", json={"vehicle_id": "TRUCK_03"})

    state = client.get("/api/state").json()
    order_id = state["orders"][1]["id"]

    # Attempt to allocate to broken down partner
    res = client.post("/api/task/allocate", json={"order_id": order_id, "vehicle_id": "TRUCK_03"})
    assert res.status_code == 200
    assert res.json()["success"] is False
    assert "BROKEN DOWN" in res.json()["error"]


def test_dashboard_api_supabase_status():
    """Verify Supabase status endpoint returns live connection to project coompycazyuaedzevyua."""
    res = client.get("/api/supabase/status")
    assert res.status_code == 200
    data = res.json()
    assert "connected" in data
    assert data["connected"] is True
    assert data["project_ref"] == "coompycazyuaedzevyua"
    assert "counts" in data
    assert "delivery_partners" in data["counts"]
    assert "orders" in data["counts"]




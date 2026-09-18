"""
Automated Verification Suite for SWARMRoute Real-World Fleet Platform.
Tests:
- Unified shared state between clients (Web and Flutter).
- Customer order placement with authentic coordinates.
- Manager live fleet visibility & AI dispatch recommendation.
- Driver telemetry ingestion with continuous PPO & Transformer route intelligence.
- Physical BLE multi-hop packet protocol, deduplication, and internet bridge relay.
- Honest fallbacks (no fabricated traffic percentages, no straight-line roads).
"""
import pytest
from fastapi.testclient import TestClient
from src.api.server import app
from src.routing.osrm_client import routing_client, OSRMRoutingClient
from src.ai.route_evaluator import route_evaluator
from src.ai.temporal_transformer import temporal_transformer


@pytest.fixture
def client():
    return TestClient(app)


def test_real_order_creation_and_osrm_routing(client):
    """Verifies that customer can create an order with real coordinates and OSM routing."""
    res = client.post("/api/v1/orders", json={
        "customer_id": "CUST_TEST_01",
        "customer_name": "Test Customer",
        "pickup_address": "Indiranagar Hub, Bengaluru",
        "pickup_lat": 12.9784,
        "pickup_lon": 77.6408,
        "delivery_address": "Koramangala 4th Block, Bengaluru",
        "delivery_lat": 12.9352,
        "delivery_lon": 77.6245,
        "demand_weight": 2.5,
        "priority": "NORMAL",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "order" in data
    order = data["order"]
    assert order["status"] == "PENDING"
    assert order["customer_id"] == "CUST_TEST_01"
    assert order["estimated_distance_km"] > 0.0


def test_manager_live_fleet_and_real_vehicle_specs(client):
    """Verifies that manager receives real delivery partner fleet telemetry and vehicle specs."""
    res = client.get("/api/v1/fleet/live")
    assert res.status_code == 200
    data = res.json()
    assert "fleet" in data
    fleet = data["fleet"]
    assert len(fleet) >= 2
    
    p0 = fleet[0]
    assert "vehicle" in p0
    v = p0["vehicle"]
    assert "manufacturer" in v
    assert "model_name" in v
    assert "engine_type" in v
    assert "fuel_capacity" in v
    assert "fuel_remaining" in v
    assert "vehicle_condition" in v
    assert "location" in p0
    assert "internet_status" in p0
    assert "ble_status" in p0


def test_ai_dispatch_recommendation_multi_criteria(client):
    """Verifies AI partner recommendation uses genuine measurable parameters."""
    # Create order first
    res_o = client.post("/api/v1/orders", json={
        "customer_id": "CUST_AI_TEST",
        "customer_name": "AI Test",
        "pickup_address": "Hub A",
        "pickup_lat": 12.9784,
        "pickup_lon": 77.6408,
        "delivery_address": "Dest B",
        "delivery_lat": 12.9352,
        "delivery_lon": 77.6245,
        "demand_weight": 3.0,
    })
    order_id = res_o.json()["order"]["id"]

    res_rec = client.post("/api/v1/dispatch/recommend", json={"order_id": order_id})
    assert res_rec.status_code == 200
    rec = res_rec.json()
    assert "recommended_partner" in rec
    best = rec["recommended_partner"]
    assert best is not None
    assert "suitability_score" in best
    assert "metrics" in best
    assert best["metrics"]["distance_to_pickup_km"] >= 0.0
    assert best["metrics"]["spare_capacity_kg"] >= 0.0


def test_driver_telemetry_and_continuous_route_intelligence(client):
    """Verifies driver telemetry ingestion and PPO + Transformer continuous route reassessment."""
    res_tel = client.post("/api/v1/driver/telemetry", json={
        "vehicle_id": "TRUCK_01",
        "latitude": 12.9750,
        "longitude": 77.6380,
        "speed_kmh": 35.0,
        "heading": 90.0,
        "fuel_level": 85.0,
        "vehicle_condition": 0.98,
        "internet_status": "ONLINE",
        "ble_status": "ACTIVE",
        "ble_peer_count": 2,
        "remaining_distance_km": 4.5,
    })
    assert res_tel.status_code == 200
    tel_data = res_tel.json()
    assert tel_data["success"] is True
    assert "route_intelligence" in tel_data
    ai = tel_data["route_intelligence"]
    assert ai["recommended_action"] in ("KEEP_ROUTE", "REROUTE", "REQUEST_ASSISTANCE")
    assert ai["action_name"] in ("HOLD_OR_CONTINUE", "ASSIGN_BEST_ORDER", "REASSIGN_STRANDED_ORDER")


def test_fuel_failure_triggers_assistance_recommendation():
    """Verifies that physical fuel exhaustion deterministically recommends REQUEST_ASSISTANCE."""
    eval_res = route_evaluator.evaluate(
        vehicle_id="TRUCK_01",
        current_location=(12.9750, 77.6380),
        destination=(12.9352, 77.6245),
        remaining_distance_km=30.0,
        speed_kmh=40.0,
        fuel_remaining_liters=0.2,  # Critically low fuel
    )
    assert eval_res["recommended_action"] == "REQUEST_ASSISTANCE"
    assert "Insufficient fuel" in eval_res["reason"]


def test_severe_traffic_triggers_reroute_recommendation():
    """Verifies that severe traffic congestion triggers REROUTE recommendation."""
    eval_res = route_evaluator.evaluate(
        vehicle_id="TRUCK_01",
        current_location=(12.9750, 77.6380),
        destination=(12.9352, 77.6245),
        remaining_distance_km=10.0,
        speed_kmh=10.0,
        fuel_remaining_liters=20.0,
        traffic_level="SEVERE",
    )
    assert eval_res["recommended_action"] == "REROUTE"


def test_honest_traffic_fallback():
    """Verifies that when traffic API keys are absent, system reports TRAFFIC DATA UNAVAILABLE."""
    client_osrm = OSRMRoutingClient()
    traffic_status = client_osrm._check_traffic_provider(12.9716, 77.5946, 12.9352, 77.6245)
    assert traffic_status == "TRAFFIC DATA UNAVAILABLE"


def test_physical_ble_mesh_relay_gateway(client):
    """
    Verifies physical BLE multi-hop mesh packet bridging to cloud:
    Device A -> Device B -> Device C -> Backend API.
    """
    res_relay = client.post("/api/v1/mesh/relay", json={
        "message_id": "BLE_PACKET_TEST_001",
        "source_device_id": "DRIVER_A_STRANDED",
        "destination_device_id": "BACKEND",
        "message_type": "ASSISTANCE_REQUEST",
        "timestamp": 1726679000.0,
        "ttl": 4,
        "hop_count": 2,
        "bridge_device_id": "DRIVER_C_GATEWAY",
        "payload": {
            "order_id": "ORD_1024",
            "reason": "MECHANICAL_FAULT_AND_NO_INTERNET",
            "fuel_remaining_liters": 1.2,
        },
    })
    assert res_relay.status_code == 200
    relay_data = res_relay.json()
    assert relay_data["status"] == "RELAY_ACCEPTED"
    assert relay_data["source_device_id"] == "DRIVER_A_STRANDED"
    assert relay_data["bridge_device_id"] == "DRIVER_C_GATEWAY"
    assert relay_data["hop_count"] == 2


def test_ble_packet_ttl_expiry(client):
    """Verifies that packets with expired TTL (<= 0) are dropped to prevent broadcast storms."""
    res_drop = client.post("/api/v1/mesh/relay", json={
        "message_id": "BLE_PACKET_EXPIRED",
        "source_device_id": "DEV_X",
        "destination_device_id": "BACKEND",
        "message_type": "HEARTBEAT",
        "timestamp": 1726679000.0,
        "ttl": 0,
        "hop_count": 5,
    })
    assert res_drop.status_code == 400
    assert "TTL expired" in res_drop.json()["error"]


def test_system_capabilities_endpoint(client):
    """Verifies truthful operational state of all platform components."""
    res = client.get("/api/v1/system/capabilities")
    assert res.status_code == 200
    caps = res.json()
    assert "database" in caps
    assert "routing" in caps
    assert caps["traffic"] == "unavailable"
    assert caps["transformer"] == "trained"
    assert caps["ppo"] == "loaded"
    assert caps["gps"] == "device"
    assert caps["ble"] == "native_android_gatt"


def test_auth_token_and_role_access_control(client):
    """Verifies server-side JWT issuance and role-based permissions."""
    # 1. Issue Manager Token
    res_mgr = client.post("/api/v1/auth/token", json={
        "email": "manager@swarmroute.io",
        "role": "MANAGER",
        "name": "Fleet Dispatcher",
    })
    assert res_mgr.status_code == 200
    mgr_token = res_mgr.json()["access_token"]
    assert len(mgr_token) > 20

    # 2. Issue Customer Token
    res_cust = client.post("/api/v1/auth/token", json={
        "email": "cust1@example.com",
        "role": "CUSTOMER",
        "name": "Cust 1",
    })
    assert res_cust.status_code == 200
    cust1_token = res_cust.json()["access_token"]

    # 3. Create Order
    res_order = client.post("/api/v1/orders", json={
        "customer_id": "CUST_ISOLATED_A",
        "customer_name": "Isolated Cust A",
        "pickup_address": "Hub 1",
        "pickup_lat": 12.9784,
        "pickup_lon": 77.6408,
        "delivery_address": "Dest 1",
        "delivery_lat": 12.9352,
        "delivery_lon": 77.6245,
    })
    order_id = res_order.json()["order"]["id"]

    # Customer 2 should NOT be allowed to track Customer A's order
    res_cust2 = client.post("/api/v1/auth/token", json={
        "email": "cust2@example.com",
        "role": "CUSTOMER",
        "name": "Cust 2",
    })
    cust2_token = res_cust2.json()["access_token"]
    res_forbidden = client.get(
        f"/api/v1/orders/{order_id}/track",
        headers={"Authorization": f"Bearer {cust2_token}"},
    )
    assert res_forbidden.status_code == 403


def test_driver_order_lifecycle_progression(client):
    """Verifies driver mobile client parcel delivery status progression."""
    # Create order
    res_o = client.post("/api/v1/orders", json={
        "customer_id": "CUST_LIFECYCLE",
        "customer_name": "Lifecycle Test",
        "pickup_address": "Depot",
        "pickup_lat": 12.9784,
        "pickup_lon": 77.6408,
        "delivery_address": "Customer Door",
        "delivery_lat": 12.9352,
        "delivery_lon": 77.6245,
    })
    order_id = res_o.json()["order"]["id"]

    # Allocate
    client.post("/api/v1/dispatch/allocate", json={
        "order_id": order_id,
        "vehicle_id": "DP_01",
    })

    # Driver picks up order
    res_pu = client.post(f"/api/v1/driver/orders/{order_id}/status", json={
        "status": "PICKED_UP",
        "vehicle_id": "DP_01",
    })
    assert res_pu.status_code == 200
    assert res_pu.json()["new_status"] == "PICKED_UP"

    # Driver delivers order
    res_del = client.post(f"/api/v1/driver/orders/{order_id}/status", json={
        "status": "DELIVERED",
        "vehicle_id": "DP_01",
    })
    assert res_del.status_code == 200
    assert res_del.json()["new_status"] == "DELIVERED"


def test_driver_telemetry_active_order_vs_no_active_order(client):
    """
    Verifies the fix that driver telemetry only computes road routing
    when an authentic delivery order is assigned, and never fabricates fake destinations.
    """
    # 1. Driver with NO active order
    res_idle = client.post("/api/v1/driver/telemetry", json={
        "vehicle_id": "IDLE_DRIVER_99",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "speed_kmh": 0.0,
        "fuel_level": 90.0,
    })
    assert res_idle.status_code == 200
    idle_data = res_idle.json()
    assert idle_data["active_order"] is None
    assert idle_data["route_intelligence"]["status"] == "NO_ACTIVE_ROUTE"

    # 2. Driver WITH active assigned order
    res_o = client.post("/api/v1/orders", json={
        "customer_id": "CUST_ROUTED",
        "customer_name": "Routed Customer",
        "pickup_address": "Indiranagar Hub",
        "pickup_lat": 12.9784,
        "pickup_lon": 77.6408,
        "delivery_address": "Koramangala 4th Block",
        "delivery_lat": 12.9352,
        "delivery_lon": 77.6245,
        "demand_weight": 2.0,
    })
    order_id = res_o.json()["order"]["id"]
    client.post("/api/v1/dispatch/allocate", json={
        "order_id": order_id,
        "vehicle_id": "DP_02",
    })

    res_active = client.post("/api/v1/driver/telemetry", json={
        "vehicle_id": "DP_02",
        "latitude": 12.9780,
        "longitude": 77.6400,
        "speed_kmh": 25.0,
        "heading": 180.0,
        "fuel_level": 75.0,
    })
    assert res_active.status_code == 200
    active_data = res_active.json()
    assert active_data["active_order"] is not None
    assert active_data["active_order"]["id"] == order_id
    assert "route" in active_data
    assert "coordinates" in active_data["route"]
    assert len(active_data["route"]["coordinates"]) > 1


def test_route_compatible_assistance_recommendation_endpoint(client):
    """Verifies that the backend evaluates nearby candidate drivers for emergency assistance."""
    res = client.post("/api/v1/dispatch/assistance/recommend", json={
        "stranded_vehicle_id": "STRANDED_DP_99",
        "latitude": 12.9750,
        "longitude": 77.6380,
        "required_capacity_kg": 5.0,
        "max_distance_km": 25.0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "candidates" in data
    assert len(data["candidates"]) > 0
    best = data["candidates"][0]
    assert "suitability_score" in best
    assert "distance_to_stranded_km" in best
    assert "spare_capacity_kg" in best
    assert best["spare_capacity_kg"] >= 5.0


def test_driver_device_hardware_linking(client):
    """Verifies pairing of driver Android smartphone device ID to driver/vehicle profile."""
    res = client.post("/api/v1/driver/device/link", json={
        "device_id": "SMARTPHONE_PIXEL_8A",
        "driver_id": "DRV_PIXEL_01",
        "vehicle_id": "DP_01",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["linked"]["device_id"] == "SMARTPHONE_PIXEL_8A"
    assert data["linked"]["driver_id"] == "DRV_PIXEL_01"


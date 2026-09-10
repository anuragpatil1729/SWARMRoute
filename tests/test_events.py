import pytest
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.fleet_state import FleetState, ConnectivityState
from src.simulation.events import EventEngine, FleetEvent, EventType


def test_event_priority_queue():
    engine = EventEngine()
    ev1 = FleetEvent(event_id="E1", event_type=EventType.NEW_ORDER, timestamp=50.0)
    ev2 = FleetEvent(event_id="E2", event_type=EventType.VEHICLE_BREAKDOWN, timestamp=10.0)
    ev3 = FleetEvent(event_id="E3", event_type=EventType.CONNECTIVITY_LOSS, timestamp=30.0)

    engine.schedule(ev1)
    engine.schedule(ev2)
    engine.schedule(ev3)

    # Pop up to T=35 mins: should get E2 (T=10) and E3 (T=30), but NOT E1 (T=50)
    due = engine.pop_due_events(35.0)
    assert len(due) == 2
    assert due[0].event_id == "E2"
    assert due[1].event_id == "E3"

    # Remaining event
    remaining = engine.pop_due_events(60.0)
    assert len(remaining) == 1
    assert remaining[0].event_id == "E1"


def test_apply_event_state_transitions():
    v = Vehicle(vehicle_id="TRUCK_01", max_weight=200.0, status=VehicleStatus.EN_ROUTE)
    fleet = FleetState(
        vehicles={"TRUCK_01": v},
        connectivity_state=ConnectivityState.CLOUD_MODE,
    )
    engine = EventEngine()

    # Breakdown event
    ev_brk = FleetEvent(
        event_id="BRK1",
        event_type=EventType.VEHICLE_BREAKDOWN,
        timestamp=20.0,
        payload={"vehicle_id": "TRUCK_01"},
    )
    engine.apply_event(ev_brk, fleet)
    assert fleet.vehicles["TRUCK_01"].status == VehicleStatus.BROKEN_DOWN

    # Connectivity loss event
    ev_loss = FleetEvent(
        event_id="NET1",
        event_type=EventType.CONNECTIVITY_LOSS,
        timestamp=25.0,
        payload={"target_mode": ConnectivityState.MESH_MODE},
    )
    engine.apply_event(ev_loss, fleet)
    assert fleet.connectivity_state == ConnectivityState.MESH_MODE

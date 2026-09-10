import pytest
from src.networking.mesh import MeshNetwork
from src.networking.messages import MeshMessage, MessageType
from src.networking.connectivity import ConnectivityManager
from src.models.fleet_state import ConnectivityState


def test_mesh_proximity_links_and_multihop():
    # Arrange 3 trucks in a line: A (0,0) <-> B (10,0) <-> C (20,0)
    # Range is 12 km.
    # A can reach B directly (dist=10 <= 12).
    # B can reach C directly (dist=10 <= 12).
    # A cannot reach C directly (dist=20 > 12).
    mesh = MeshNetwork(transmission_range_km=12.0, packet_loss_per_hop=0.0, seed=42)
    mesh.update_node_position("TRUCK_A", (0.0, 0.0))
    mesh.update_node_position("TRUCK_B", (10.0, 0.0))
    mesh.update_node_position("TRUCK_C", (20.0, 0.0))

    topo = mesh.build_topology()
    assert topo.has_edge("TRUCK_A", "TRUCK_B")
    assert topo.has_edge("TRUCK_B", "TRUCK_C")
    assert not topo.has_edge("TRUCK_A", "TRUCK_C")  # Beyond single-hop radio range

    # Transmit message from A to C: must route through B (2 hops)
    msg = MeshMessage(
        message_id="M1",
        message_type=MessageType.SOS_BREAKDOWN,
        sender_id="TRUCK_A",
        receiver_id="TRUCK_C",
        timestamp_mins=10.0,
    )
    success = mesh.transmit(msg)
    assert success is True
    assert msg.delivered is True
    assert msg.hop_count == 2
    assert msg.route_taken == ["TRUCK_A", "TRUCK_B", "TRUCK_C"]
    assert msg.total_latency_ms > 0.0


def test_mesh_node_failure_reroute():
    mesh = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.0, seed=42)
    # Triangular network: A <-> B <-> C, and A <-> D <-> C
    mesh.update_node_position("A", (0.0, 0.0))
    mesh.update_node_position("B", (10.0, 5.0))
    mesh.update_node_position("D", (10.0, -5.0))
    mesh.update_node_position("C", (20.0, 0.0))

    # Node B breaks down
    mesh.set_node_failed("B", failed=True)

    msg = MeshMessage(
        message_id="M2",
        message_type=MessageType.ORDER_TRANSFER_REQUEST,
        sender_id="A",
        receiver_id="C",
        timestamp_mins=15.0,
    )
    success = mesh.transmit(msg)
    assert success is True
    assert "B" not in msg.route_taken
    assert msg.route_taken == ["A", "D", "C"]


def test_mesh_packet_loss_drop():
    # 100% loss should drop packet
    mesh = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=1.0, seed=42)
    mesh.update_node_position("A", (0.0, 0.0))
    mesh.update_node_position("B", (5.0, 0.0))
    msg = MeshMessage(
        message_id="M_LOSS",
        message_type=MessageType.ORDER_TRANSFER_REQUEST,
        sender_id="A",
        receiver_id="B",
        timestamp_mins=5.0,
    )
    success = mesh.transmit(msg)
    assert success is False
    assert msg.delivered is False


def test_connectivity_mode_transitions():
    conn = ConnectivityManager(initial_state=ConnectivityState.CLOUD_MODE)
    assert conn.current_state == ConnectivityState.CLOUD_MODE

    # Cloud lost
    conn.on_cloud_lost()
    assert conn.current_state == ConnectivityState.MESH_MODE

    # Buffer a message while offline
    msg = MeshMessage(
        message_id="M3",
        message_type=MessageType.STATE_SYNC,
        sender_id="A",
        timestamp_mins=30.0,
    )
    conn.buffer_message(msg)
    assert len(conn.sync_buffer) == 1

    # Reconnected to cloud
    state, synced = conn.on_cloud_restored()
    assert state == ConnectivityState.CLOUD_MODE
    assert len(synced) == 1
    assert len(conn.sync_buffer) == 0

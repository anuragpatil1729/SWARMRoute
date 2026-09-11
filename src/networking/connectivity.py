from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from src.models.fleet_state import ConnectivityState
from src.networking.messages import MeshMessage


class ConnectivityManager:
    """
    Manages fleet communication topologies and seamless mode transitions:
      CLOUD_MODE (Centralized Cellular/Internet)
        ↓ (loss of cloud gateway)
      EDGE_MODE (Local depot coordinator)
        ↓ (out of range of depot)
      MESH_MODE (Peer-to-Peer Truck Mesh)
        ↓ (partitioned / isolated node)
      DISCONNECTED_MODE (Autonomous Local Fallback)
    """

    def __init__(self, initial_state: ConnectivityState = ConnectivityState.CLOUD_MODE) -> None:
        self.current_state = initial_state
        self.sync_buffer: List[MeshMessage] = []
        self.state_history: List[ConnectivityState] = [initial_state]

    def transition_to(self, new_state: ConnectivityState) -> None:
        if new_state != self.current_state:
            self.current_state = new_state
            self.state_history.append(new_state)

    def on_cloud_lost(self) -> ConnectivityState:
        """Triggered upon loss of central Internet / cloud uplink."""
        self.transition_to(ConnectivityState.MESH_MODE)
        return self.current_state

    def on_cloud_restored(self) -> Tuple[ConnectivityState, List[MeshMessage]]:
        """
        Triggered when Internet connectivity returns.
        Dispatches all cached peer-to-peer actions from MESH_MODE to the central cloud.
        """
        self.transition_to(ConnectivityState.CLOUD_MODE)
        synced = list(self.sync_buffer)
        self.sync_buffer.clear()
        return self.current_state, synced

    def buffer_message(self, message: MeshMessage) -> None:
        """Buffers peer-to-peer actions for future cloud synchronization."""
        self.sync_buffer.append(message)

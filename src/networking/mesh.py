from __future__ import annotations
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

from src.networking.messages import MeshMessage, MessageType


class MeshNetwork:
    """
    Simulated Truck-to-Truck Multi-hop Mesh Network.
    Models:
      - Ad-hoc radio transmission range between moving vehicles.
      - Shortest-path multi-hop message forwarding (e.g. AODV / wireless mesh).
      - Cumulative latency per hop and stochastic packet loss.
      - Dynamic node failures (offline/broken trucks) and link disruptions.
    """

    def __init__(
        self,
        transmission_range_km: float = 25.0,
        base_latency_per_hop_ms: float = 20.0,
        packet_loss_per_hop: float = 0.03,
        seed: Optional[int] = 42,
    ) -> None:
        self.transmission_range_km = transmission_range_km
        self.base_latency_per_hop_ms = base_latency_per_hop_ms
        self.packet_loss_per_hop = packet_loss_per_hop
        self.rng = random.Random(seed)

        self.nodes: Dict[str, Tuple[float, float]] = {}  # vehicle_id -> (x, y)
        self.failed_nodes: Set[str] = set()
        self.failed_links: Set[Tuple[str, str]] = set()
        self.topology: nx.Graph = nx.Graph()

    def update_node_position(self, node_id: str, position: Tuple[float, float]) -> None:
        self.nodes[node_id] = position

    def set_node_failed(self, node_id: str, failed: bool = True) -> None:
        if failed:
            self.failed_nodes.add(node_id)
        else:
            self.failed_nodes.discard(node_id)

    def set_link_failed(self, u: str, v: str, failed: bool = True) -> None:
        link = tuple(sorted([u, v]))
        if failed:
            self.failed_links.add(link)
        else:
            self.failed_links.discard(link)

    def build_topology(self) -> nx.Graph:
        """
        Reconstructs the active mesh topology based on physical proximity
        and operational node/link health.
        """
        self.topology = nx.Graph()
        node_ids = list(self.nodes.keys())

        for n_id in node_ids:
            self.topology.add_node(n_id, pos=self.nodes[n_id], is_failed=(n_id in self.failed_nodes))

        # Create links for pairs within transmission range
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                u, v = node_ids[i], node_ids[j]
                if u in self.failed_nodes or v in self.failed_nodes:
                    continue
                link = tuple(sorted([u, v]))
                if link in self.failed_links:
                    continue

                pos_u = self.nodes[u]
                pos_v = self.nodes[v]
                dist = math.hypot(pos_u[0] - pos_v[0], pos_u[1] - pos_v[1])

                if dist <= self.transmission_range_km:
                    self.topology.add_edge(u, v, distance=dist, weight=dist)

        return self.topology

    def transmit(self, message: MeshMessage) -> bool:
        """
        Routes message from sender to receiver across multi-hop links.
        If receiver is 'BROADCAST', broadcasts across the connected component.
        """
        self.build_topology()
        sender = message.sender_id

        if sender not in self.nodes:
            message.delivered = False
            return False

        if message.receiver_id == "BROADCAST":
            # Check reachable neighbors in the connected component
            if self.topology.has_node(sender):
                reachable = nx.descendants(self.topology, sender)
                message.hop_count = 1 if reachable else 0
                message.delivered = len(reachable) > 0
                message.total_latency_ms = self.base_latency_per_hop_ms
                message.route_taken = [sender] + list(reachable)
                return message.delivered
            message.delivered = False
            return False

        receiver = message.receiver_id
        if not self.topology.has_node(sender) or not self.topology.has_node(receiver):
            message.delivered = False
            return False

        if not nx.has_path(self.topology, sender, receiver):
            message.delivered = False
            return False

        # Shortest hop path
        path = nx.shortest_path(self.topology, sender, receiver)
        hops = len(path) - 1
        message.hop_count = hops
        message.route_taken = path

        # Simulate latency and packet loss along the path
        latency = 0.0
        for _ in range(hops):
            latency += self.base_latency_per_hop_ms + self.rng.uniform(1.0, 5.0)
            if self.rng.random() < self.packet_loss_per_hop:
                # Packet dropped mid-flight
                message.delivered = False
                message.total_latency_ms = latency
                return False

        message.total_latency_ms = latency
        message.delivered = True
        return True

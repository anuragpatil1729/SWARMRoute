from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    SOS_BREAKDOWN = "SOS_BREAKDOWN"
    ORDER_TRANSFER_REQUEST = "ORDER_TRANSFER_REQUEST"
    ORDER_TRANSFER_ACCEPT = "ORDER_TRANSFER_ACCEPT"
    TRAFFIC_ALERT = "TRAFFIC_ALERT"
    HEARTBEAT = "HEARTBEAT"
    STATE_SYNC = "STATE_SYNC"


class MeshMessage(BaseModel):
    """
    Standard packet transmitted over the simulated truck-to-truck mesh network.
    """
    message_id: str
    message_type: MessageType
    sender_id: str
    receiver_id: str = "BROADCAST"  # "BROADCAST" or specific vehicle ID
    timestamp_mins: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    hop_count: int = 0
    route_taken: List[str] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    delivered: bool = False

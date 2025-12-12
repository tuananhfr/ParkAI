"""
P2P Protocol - Message types và validation
"""
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
import json


class MessageType(str, Enum):
    """P2P Message types"""
    # Vehicle events
    VEHICLE_ENTRY_PENDING = "VEHICLE_ENTRY_PENDING"
    VEHICLE_ENTRY_CONFIRMED = "VEHICLE_ENTRY_CONFIRMED"
    VEHICLE_EXIT = "VEHICLE_EXIT"
    LOCATION_UPDATE = "LOCATION_UPDATE"  # PARKING_LOT camera location tracking
    PARKING_LOT_CONFIG = "PARKING_LOT_CONFIG"  # PARKING_LOT camera config update

    # History admin operations
    HISTORY_UPDATE = "HISTORY_UPDATE"
    HISTORY_DELETE = "HISTORY_DELETE"

    # Sync & Health
    HEARTBEAT = "HEARTBEAT"
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_RESPONSE = "SYNC_RESPONSE"

    # Config & State
    CONFIG_UPDATE = "CONFIG_UPDATE"
    SUBSCRIPTION_UPDATE = "SUBSCRIPTION_UPDATE"


class P2PMessage:
    """P2P Message wrapper"""

    def __init__(
        self,
        msg_type: MessageType,
        source_central: str,
        timestamp: Optional[int] = None,
        event_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        self.type = msg_type
        self.source_central = source_central
        self.timestamp = timestamp or int(datetime.now().timestamp() * 1000)
        self.event_id = event_id
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "type": self.type,
            "source_central": self.source_central,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "data": self.data
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'P2PMessage':
        """Create message from dictionary"""
        return cls(
            msg_type=data.get("type"),
            source_central=data.get("source_central"),
            timestamp=data.get("timestamp"),
            event_id=data.get("event_id"),
            data=data.get("data", {})
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'P2PMessage':
        """Create message from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


def create_entry_pending_message(
    source_central: str,
    event_id: str,
    plate_id: str,
    plate_view: str,
    edge_id: str,
    camera_type: str,
    direction: str,
    entry_time: str,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create VEHICLE_ENTRY_PENDING message"""
    return P2PMessage(
        msg_type=MessageType.VEHICLE_ENTRY_PENDING,
        source_central=source_central,
        timestamp=timestamp,
        event_id=event_id,
        data={
            "plate_id": plate_id,
            "plate_view": plate_view,
            "edge_id": edge_id,
            "camera_type": camera_type,
            "direction": direction,
            "entry_time": entry_time
        }
    )


def create_entry_confirmed_message(
    source_central: str,
    event_id: str,
    confirmed_time: str,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create VEHICLE_ENTRY_CONFIRMED message"""
    return P2PMessage(
        msg_type=MessageType.VEHICLE_ENTRY_CONFIRMED,
        source_central=source_central,
        timestamp=timestamp,
        event_id=event_id,
        data={
            "confirmed_time": confirmed_time
        }
    )


def create_exit_message(
    source_central: str,
    event_id: str,
    plate_id: str,
    exit_central: str,
    exit_edge: str,
    exit_time: str,
    fee: int,
    duration: str,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create VEHICLE_EXIT message"""
    return P2PMessage(
        msg_type=MessageType.VEHICLE_EXIT,
        source_central=source_central,
        timestamp=timestamp,
        event_id=event_id,
        data={
            "plate_id": plate_id,
            "exit_central": exit_central,
            "exit_edge": exit_edge,
            "exit_time": exit_time,
            "fee": fee,
            "duration": duration
        }
    )


def create_history_update_message(
    source_central: str,
    history_id: int,
    plate_text: str,
    plate_view: str,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create HISTORY_UPDATE message for admin edits"""
    return P2PMessage(
        msg_type=MessageType.HISTORY_UPDATE,
        source_central=source_central,
        timestamp=timestamp,
        event_id=None,
        data={
            "history_id": history_id,
            "plate_text": plate_text,
            "plate_view": plate_view
        }
    )


def create_history_delete_message(
    source_central: str,
    history_id: int,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create HISTORY_DELETE message for admin deletes"""
    return P2PMessage(
        msg_type=MessageType.HISTORY_DELETE,
        source_central=source_central,
        timestamp=timestamp,
        event_id=None,
        data={
            "history_id": history_id
        }
    )


def create_location_update_message(
    source_central: str,
    event_id: str,
    plate_id: str,
    location: str,
    location_time: str,
    is_anomaly: bool = False,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create LOCATION_UPDATE message for PARKING_LOT camera detections"""
    return P2PMessage(
        msg_type=MessageType.LOCATION_UPDATE,
        source_central=source_central,
        timestamp=timestamp,
        event_id=event_id,
        data={
            "plate_id": plate_id,
            "location": location,
            "location_time": location_time,
            "is_anomaly": is_anomaly
        }
    )


def create_parking_lot_config_message(
    source_central: str,
    location_name: str,
    capacity: int,
    camera_id: int,
    camera_type: str = "PARKING_LOT",
    edge_id: Optional[str] = None,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """
    Create PARKING_LOT_CONFIG message to sync parking lot metadata across centrals.
    """
    return P2PMessage(
        msg_type=MessageType.PARKING_LOT_CONFIG,
        source_central=source_central,
        timestamp=timestamp,
        data={
            "location_name": location_name,
            "capacity": capacity,
            "camera_id": camera_id,
            "camera_type": camera_type,
            "edge_id": edge_id,
        },
    )


def create_heartbeat_message(
    source_central: str,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create HEARTBEAT message"""
    return P2PMessage(
        msg_type=MessageType.HEARTBEAT,
        source_central=source_central,
        timestamp=timestamp,
        data={}
    )


def create_sync_request_message(
    source_central: str,
    since_timestamp: int,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create SYNC_REQUEST message"""
    return P2PMessage(
        msg_type=MessageType.SYNC_REQUEST,
        source_central=source_central,
        timestamp=timestamp,
        data={
            "since_timestamp": since_timestamp
        }
    )


def create_sync_response_message(
    source_central: str,
    events: list,
    timestamp: Optional[int] = None
) -> P2PMessage:
    """Create SYNC_RESPONSE message"""
    return P2PMessage(
        msg_type=MessageType.SYNC_RESPONSE,
        source_central=source_central,
        timestamp=timestamp,
        data={
            "events": events
        }
    )


def validate_message(message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate P2P message

    Returns:
        (is_valid, error_message)
    """
    # Check required fields
    if "type" not in message:
        return False, "Missing 'type' field"

    if "source_central" not in message:
        return False, "Missing 'source_central' field"

    if "timestamp" not in message:
        return False, "Missing 'timestamp' field"

    # Validate message type
    try:
        msg_type = MessageType(message["type"])
    except ValueError:
        return False, f"Invalid message type: {message['type']}"

    # Validate specific message types
    if msg_type in [MessageType.VEHICLE_ENTRY_PENDING, MessageType.VEHICLE_ENTRY_CONFIRMED, MessageType.VEHICLE_EXIT]:
        if "event_id" not in message:
            return False, "Missing 'event_id' for vehicle event"

    return True, None

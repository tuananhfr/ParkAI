"""
Data models cho application
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class ConnectionStatus:
    """Backend connection status"""
    connected: bool
    backend_type: Optional[str] = None  # "central" hoặc "edge"
    last_check: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class Stats:
    """Dashboard statistics"""
    entries_today: int = 0
    exits_today: int = 0
    vehicles_in_parking: int = 0
    revenue_today: float = 0.0


@dataclass
class Camera:
    """Camera info"""
    id: int
    name: str
    location: str
    stream_url: Optional[str] = None
    status: str = "offline"  # "online", "offline"
    current_plate: Optional[str] = None
    vehicle_type: Optional[str] = None
    entry_time: Optional[str] = None


@dataclass
class HistoryEntry:
    """History entry/exit record"""
    id: int
    plate: str
    vehicle_type: str
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    fee: float = 0.0
    camera_id: int = 0

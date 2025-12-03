"""
P2P Parking Integration - Wrapper để broadcast parking events
"""
from datetime import datetime
from typing import Optional
from .protocol import (
    create_entry_pending_message,
    create_entry_confirmed_message,
    create_exit_message
)


class P2PParkingBroadcaster:
    """Broadcast parking events qua P2P"""

    def __init__(self, p2p_manager, central_id: str):
        self.p2p_manager = p2p_manager
        self.central_id = central_id

    def generate_event_id(self, plate_id: str) -> str:
        """
        Generate unique event_id

        Format: central-1_timestamp_plate_id
        Example: central-1_1733140800000_29A12345
        """
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        return f"{self.central_id}_{timestamp_ms}_{plate_id}"

    async def broadcast_entry_pending(
        self,
        event_id: str,
        plate_id: str,
        plate_view: str,
        edge_id: str,
        camera_type: str,
        direction: str,
        entry_time: str
    ):
        """
        Broadcast VEHICLE_ENTRY_PENDING event

        Call này NGAY SAU KHI insert vào local DB
        """
        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            # Standalone mode - không broadcast
            return

        try:
            message = create_entry_pending_message(
                source_central=self.central_id,
                event_id=event_id,
                plate_id=plate_id,
                plate_view=plate_view,
                edge_id=edge_id,
                camera_type=camera_type,
                direction=direction,
                entry_time=entry_time
            )

            await self.p2p_manager.broadcast(message)
            print(f"📡 Broadcasted ENTRY_PENDING: {plate_view} ({event_id})")

        except Exception as e:
            print(f"❌ Error broadcasting entry pending: {e}")

    async def broadcast_entry_confirmed(
        self,
        event_id: str,
        confirmed_time: str
    ):
        """
        Broadcast VEHICLE_ENTRY_CONFIRMED event

        Call này khi barrier đã đóng
        """
        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            return

        try:
            message = create_entry_confirmed_message(
                source_central=self.central_id,
                event_id=event_id,
                confirmed_time=confirmed_time
            )

            await self.p2p_manager.broadcast(message)
            print(f"📡 Broadcasted ENTRY_CONFIRMED: {event_id}")

        except Exception as e:
            print(f"❌ Error broadcasting entry confirmed: {e}")

    async def broadcast_exit(
        self,
        event_id: str,
        exit_edge: str,
        exit_time: str,
        fee: int,
        duration: str
    ):
        """
        Broadcast VEHICLE_EXIT event

        Call này NGAY SAU KHI update exit vào local DB
        """
        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            return

        try:
            message = create_exit_message(
                source_central=self.central_id,
                event_id=event_id,
                exit_central=self.central_id,
                exit_edge=exit_edge,
                exit_time=exit_time,
                fee=fee,
                duration=duration
            )

            await self.p2p_manager.broadcast(message)
            print(f"📡 Broadcasted EXIT: {event_id}, fee {fee}")

        except Exception as e:
            print(f"❌ Error broadcasting exit: {e}")

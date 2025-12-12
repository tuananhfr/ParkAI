"""
P2P Parking Integration - Wrapper để broadcast parking events
"""
from datetime import datetime
from typing import Optional
from .protocol import (
    create_entry_pending_message,
    create_entry_confirmed_message,
    create_exit_message,
    create_history_update_message,
    create_history_delete_message,
    create_location_update_message,
    create_parking_lot_config_message,
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
            # Standalone mode - khong broadcast
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
            print(f"Broadcasted ENTRY_PENDING: {plate_view} ({event_id})")

        except Exception as e:
            print(f"Error broadcasting entry pending: {e}")

    async def broadcast_entry_confirmed(
        self,
        event_id: str,
        confirmed_time: str
    ):
        """
        Broadcast VEHICLE_ENTRY_CONFIRMED event
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
            print(f"Broadcasted ENTRY_CONFIRMED: {event_id}")

        except Exception as e:
            print(f"Error broadcasting entry confirmed: {e}")

    async def broadcast_exit(
        self,
        event_id: str,
        plate_id: str,
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
                plate_id=plate_id,
                exit_central=self.central_id,
                exit_edge=exit_edge,
                exit_time=exit_time,
                fee=fee,
                duration=duration
            )

            await self.p2p_manager.broadcast(message)
            print(f"Broadcasted EXIT: {event_id}, fee {fee}")

        except Exception as e:
            print(f"Error broadcasting exit: {e}")

    async def broadcast_history_update(
        self,
        history_id: int,
        plate_text: str,
        plate_view: str
    ):
        """
        Broadcast HISTORY_UPDATE event (admin edit)

        Call này khi admin sửa record trên Central
        """
        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            return

        try:
            message = create_history_update_message(
                source_central=self.central_id,
                history_id=history_id,
                plate_text=plate_text,
                plate_view=plate_view
            )

            await self.p2p_manager.broadcast(message)
            print(f"Broadcasted HISTORY_UPDATE: record {history_id}")

        except Exception as e:
            print(f"Error broadcasting history update: {e}")

    async def broadcast_history_delete(
        self,
        history_id: int
    ):
        """
        Broadcast HISTORY_DELETE event (admin delete)

        Call này khi admin xóa record trên Central
        """
        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            return

        try:
            message = create_history_delete_message(
                source_central=self.central_id,
                history_id=history_id
            )

            await self.p2p_manager.broadcast(message)
            print(f"Broadcasted HISTORY_DELETE: record {history_id}")

        except Exception as e:
            print(f"Error broadcasting history delete: {e}")

    async def broadcast_location_update(
        self,
        event_id: str,
        plate_id: str,
        location: str,
        location_time: str,
        is_anomaly: bool = False
    ):
        """
        Broadcast LOCATION_UPDATE event (PARKING_LOT camera detection)

        Call này khi PARKING_LOT camera detect xe và update location
        """
        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            return

        try:
            message = create_location_update_message(
                source_central=self.central_id,
                event_id=event_id,
                plate_id=plate_id,
                location=location,
                location_time=location_time,
                is_anomaly=is_anomaly
            )

            await self.p2p_manager.broadcast(message)
            print(f"Broadcasted LOCATION_UPDATE: {plate_id} at {location}")

        except Exception as e:
            print(f"Error broadcasting location update: {e}")

    async def broadcast_parking_lot_config(
        self,
        location_name: str,
        capacity: int,
        camera_id: int,
        camera_type: str = "PARKING_LOT",
        edge_id: Optional[str] = None
    ):
        """
        Broadcast PARKING_LOT_CONFIG event (parking lot config update)

        Call này khi Edge sync parking lot config lên Central
        """
        print(f"[P2P DEBUG] broadcast_parking_lot_config called: {location_name}, capacity={capacity}")
        print(f"[P2P DEBUG] p2p_manager: {self.p2p_manager}")
        print(f"[P2P DEBUG] is_standalone: {self.p2p_manager.config.is_standalone() if self.p2p_manager else 'N/A'}")

        if not self.p2p_manager or self.p2p_manager.config.is_standalone():
            print("[P2P DEBUG] Skipping broadcast - standalone mode or no p2p_manager")
            return

        try:
            # Use P2PMessage helper to ensure correct serialization
            message = create_parking_lot_config_message(
                source_central=self.central_id,
                location_name=location_name,
                capacity=capacity,
                camera_id=camera_id,
                camera_type=camera_type,
                edge_id=edge_id,
            )

            print(f"[P2P DEBUG] Broadcasting message: {message.to_dict()}")
            await self.p2p_manager.broadcast(message)
            print(f"Broadcasted PARKING_LOT_CONFIG: {location_name}, capacity={capacity}")

        except Exception as e:
            print(f"Error broadcasting parking lot config: {e}")

"""
P2P Event Handler - Xử lý events nhận từ peer centrals
"""
from typing import Optional
from datetime import datetime
import traceback
import asyncio

from .protocol import P2PMessage, MessageType


class P2PEventHandler:
    """Handler cho P2P events"""

    def __init__(self, database, this_central_id: str, on_history_update=None, on_edge_broadcast=None):
        self.db = database
        # Alias cho các handler mới để tránh AttributeError khi dùng self.database
        self.database = database
        self.this_central_id = this_central_id
        # Callback async (vd: broadcast_history_update) để bắn WebSocket cho UI
        self.on_history_update = on_history_update
        # Callback async để broadcast events xuống Edge backends
        self.on_edge_broadcast = on_edge_broadcast

    async def handle_vehicle_entry_pending(self, message: P2PMessage):
        """
        Handle VEHICLE_ENTRY_PENDING từ peer

        Message data:
        {
            "plate_id": "29A12345",
            "plate_view": "29A-123.45",
            "edge_id": "edge-1",
            "camera_type": "car",
            "direction": "ENTRY",
            "entry_time": "2025-12-02 10:30:00"
        }
        """
        try:
            event_id = message.event_id
            source_central = message.source_central
            data = message.data

            plate_id = data.get("plate_id")
            plate_view = data.get("plate_view")
            edge_id = data.get("edge_id")
            entry_time = data.get("entry_time")

            # Check duplicate - neu da co event_id nay roi thi skip
            if self._event_exists(event_id):
                print(f"Event {event_id} already exists, skipping")
                return

            # Check conflict - neu xe nay da vao tu central khac
            existing = self.db.find_vehicle_in_parking(plate_id)
            if existing:
                # Conflict detected - so sanh timestamp
                await self._resolve_conflict(existing, message)
                return

            # No conflict - insert remote entry
            self.db.add_vehicle_entry_p2p(
                event_id=event_id,
                source_central=source_central,
                edge_id=edge_id,
                plate_id=plate_id,
                plate_view=plate_view,
                entry_time=entry_time,
                camera_id=None,  # Edge camera, khong co camera_id cua central
                camera_name=f"{source_central}/{edge_id}",
                confidence=0.0,  # Unknown tu remote
                source="p2p_sync"
            )

            print(f"Synced ENTRY from {source_central}: {plate_view} ({event_id})")

            await self._emit_history_update({
                "type": "p2p_entry_synced",
                "event_id": event_id,
                "source_central": source_central,
                "edge_id": edge_id,
                "plate_id": plate_id,
                "direction": "ENTRY",
                "entry_time": entry_time,
                "event_type": "ENTRY",
            })

            # Broadcast to Edge backends
            await self._broadcast_to_edges({
                "type": "ENTRY",
                "event_id": event_id,
                "source_central": source_central,
                "camera_id": edge_id,
                "camera_name": f"{source_central}/{edge_id}",
                "camera_type": data.get("camera_type", "ENTRY"),
                "data": {
                    "plate_text": plate_id,
                    "plate_view": plate_view,
                    "confidence": 0.0,
                    "source": "p2p_sync"
                },
                "entry_time": entry_time,
            })

        except Exception as e:
            print(f"Error handling VEHICLE_ENTRY_PENDING: {e}")
            traceback.print_exc()

    async def handle_vehicle_entry_confirmed(self, message: P2PMessage):
        """
        Handle VEHICLE_ENTRY_CONFIRMED từ peer

        Message data:
        {
            "confirmed_time": "2025-12-02 10:30:15"
        }
        """
        try:
            event_id = message.event_id
            confirmed_time = message.data.get("confirmed_time")

            # Update entry status to CONFIRMED
            # (Trong design hien tai, PENDING va CONFIRMED deu la status='IN')

            # Hien tai chi log
            print(f"Entry {event_id} confirmed at {confirmed_time}")

        except Exception as e:
            print(f"Error handling VEHICLE_ENTRY_CONFIRMED: {e}")
            traceback.print_exc()

    async def handle_vehicle_exit(self, message: P2PMessage):
        """
        Handle VEHICLE_EXIT từ peer

        Message data:
        {
            "exit_central": "central-5",
            "exit_edge": "edge-20",
            "exit_time": "2025-12-02 11:30:00",
            "fee": 25000,
            "duration": "1 giờ 0 phút"
        }
        """
        try:
            event_id = message.event_id
            data = message.data

            exit_central = data.get("exit_central")
            exit_edge = data.get("exit_edge")
            exit_time = data.get("exit_time")
            fee = data.get("fee", 0)
            duration = data.get("duration", "")

            # Try to find entry by event_id first
            entry = self.db.find_history_by_event_id(event_id)

            # Fallback: nếu không tìm thấy bằng event_id, tìm bằng plate_id
            plate_id_from_data = data.get("plate_id")
            if not entry and plate_id_from_data:
                entry = self.db.find_vehicle_in_parking(plate_id_from_data)

            # Update exit info
            # Nếu tìm thấy entry bằng plate_id (fallback), dùng update_vehicle_exit thông thường
            if entry and not self.db.find_history_by_event_id(event_id):
                # Fallback path: update by plate_id
                success = self.db.update_vehicle_exit(
                    plate_id=plate_id_from_data,
                    exit_time=exit_time,
                    camera_id=None,
                    camera_name=f"{exit_central}/{exit_edge}",
                    confidence=0.0,
                    source="p2p_sync",
                    duration=duration,
                    fee=fee
                )
            else:
                # Normal path: update by event_id
                success = self.db.update_vehicle_exit_p2p(
                    event_id=event_id,
                    exit_time=exit_time,
                    camera_id=None,
                    camera_name=f"{exit_central}/{exit_edge}",
                    confidence=0.0,
                    source="p2p_sync",
                    duration=duration,
                    fee=fee
                )

            if success:
                print(f"Synced EXIT from {exit_central}: event {event_id}, fee {fee}")
                await self._emit_history_update({
                    "type": "p2p_exit_synced",
                    "event_id": event_id,
                    "exit_central": exit_central,
                    "exit_edge": exit_edge,
                    "exit_time": exit_time,
                    "fee": fee,
                    "event_type": "EXIT",
                })

                # Broadcast to Edge backends
                await self._broadcast_to_edges({
                    "type": "EXIT",
                    "event_id": event_id,
                    "source_central": exit_central,
                    "camera_id": exit_edge,
                    "camera_name": f"{exit_central}/{exit_edge}",
                    "camera_type": "EXIT",
                    "data": {
                        "source": "p2p_sync"
                    },
                    "exit_time": exit_time,
                    "fee": fee,
                    "duration": duration,
                })
            else:
                print(f"Failed to update exit for event {event_id} - entry not found")

        except Exception as e:
            print(f"Error handling VEHICLE_EXIT: {e}")
            traceback.print_exc()

    async def _resolve_conflict(self, existing_entry: dict, new_message: P2PMessage):
        """
        Resolve conflict khi 2 centrals cùng detect 1 xe

        Strategy: Giữ entry CŨ HƠN (timestamp nhỏ hơn)
        """
        try:
            existing_event_id = existing_entry.get("event_id")
            new_event_id = new_message.event_id

            if not existing_event_id:
                # Entry cu khong co event_id (tao truoc khi co P2P)
                # Giu entry cu
                print(f"Conflict: Keeping old entry (no event_id)")
                return

            # Parse timestamp tu event_id (format: central-1_timestamp_plate_id)
            existing_timestamp = self._parse_timestamp_from_event_id(existing_event_id)
            new_timestamp = self._parse_timestamp_from_event_id(new_event_id)

            if existing_timestamp is None or new_timestamp is None:
                print(f"Cannot parse timestamp, keeping existing entry")
                return

            if new_timestamp < existing_timestamp:
                # Event moi CU HON → xoa entry hien tai, insert entry moi
                print(f"Conflict: New entry is older, replacing local entry")
                print(f"   Old: {existing_event_id} (ts={existing_timestamp})")
                print(f"   New: {new_event_id} (ts={new_timestamp})")

                # Delete existing
                self.db.delete_entry_by_event_id(existing_event_id)

                # Insert new
                data = new_message.data
                self.db.add_vehicle_entry_p2p(
                    event_id=new_event_id,
                    source_central=new_message.source_central,
                    edge_id=data.get("edge_id"),
                    plate_id=data.get("plate_id"),
                    plate_view=data.get("plate_view"),
                    entry_time=data.get("entry_time"),
                    camera_id=None,
                    camera_name=f"{new_message.source_central}/{data.get('edge_id')}",
                    confidence=0.0,
                    source="p2p_sync"
                )

                print(f"Replaced with older entry from {new_message.source_central}")
                await self._emit_history_update({
                    "type": "p2p_entry_replaced",
                    "event_id": new_event_id,
                    "source_central": new_message.source_central,
                    "edge_id": data.get("edge_id"),
                    "plate_id": data.get("plate_id"),
                    "entry_time": data.get("entry_time"),
                })

            else:
                # Entry hien tai CU HON → giu nguyen, ignore message moi
                print(f"Conflict: Local entry is older, ignoring new entry")
                print(f"   Local: {existing_event_id} (ts={existing_timestamp})")
                print(f"   Remote: {new_event_id} (ts={new_timestamp})")

        except Exception as e:
            print(f"Error resolving conflict: {e}")
            traceback.print_exc()

    def _event_exists(self, event_id: str) -> bool:
        """Check if event_id already exists in database"""
        return self.db.event_exists(event_id)

    def _parse_timestamp_from_event_id(self, event_id: str) -> Optional[int]:
        """
        Parse timestamp từ event_id

        Format: central-1_1733140800000_29A12345
        Return: 1733140800000 (int)
        """
        try:
            parts = event_id.split("_")
            if len(parts) >= 2:
                return int(parts[1])
            return None
        except:
            return None

    async def handle_history_update(self, message: P2PMessage):
        """
        Handle HISTORY_UPDATE từ P2P peer (admin sửa record)
        """
        try:
            source_central = message.source_central
            data = message.data
            history_id = data.get("history_id")
            plate_text = data.get("plate_text")
            plate_view = data.get("plate_view")

            print(f"[P2P] Received HISTORY_UPDATE from {source_central}: record {history_id}")

            # Update local DB
            if self.db.update_history_entry(history_id, plate_text, plate_view):
                print(f"[P2P] Updated record {history_id} in local DB")

                # Broadcast to frontend
                await self._emit_history_update({"type": "updated", "history_id": history_id})

                # Broadcast to Edges
                await self._broadcast_to_edges({
                    "type": "UPDATE",
                    "history_id": history_id,
                    "data": {
                        "plate_text": plate_text,
                        "plate_view": plate_view
                    }
                })
            else:
                print(f"[P2P] Failed to update record {history_id}")

        except Exception as e:
            print(f"Error handling HISTORY_UPDATE: {e}")
            import traceback
            traceback.print_exc()

    async def handle_history_delete(self, message: P2PMessage):
        """
        Handle HISTORY_DELETE từ P2P peer (admin xóa record)
        """
        try:
            source_central = message.source_central
            data = message.data
            history_id = data.get("history_id")

            print(f"[P2P] Received HISTORY_DELETE from {source_central}: record {history_id}")

            # Delete from local DB
            if self.db.delete_history_entry(history_id):
                print(f"[P2P] Deleted record {history_id} from local DB")

                # Broadcast to frontend
                await self._emit_history_update({"type": "deleted", "history_id": history_id})

                # Broadcast to Edges
                await self._broadcast_to_edges({
                    "type": "DELETE",
                    "history_id": history_id
                })
            else:
                print(f"[P2P] Failed to delete record {history_id}")

        except Exception as e:
            print(f"Error handling HISTORY_DELETE: {e}")
            import traceback
            traceback.print_exc()

    async def handle_location_update(self, message: P2PMessage):
        """
        Handle LOCATION_UPDATE từ P2P peer (PARKING_LOT camera detection)
        """
        try:
            source_central = message.source_central
            event_id = message.event_id
            data = message.data
            plate_id = data.get("plate_id")
            location = data.get("location")
            location_time = data.get("location_time")
            is_anomaly = data.get("is_anomaly", False)

            print(f"[P2P] Received LOCATION_UPDATE from {source_central}: {plate_id} at {location}")

            # Check if vehicle is in parking lot
            vehicle = self.db.find_vehicle_in_parking(plate_id)

            if vehicle:
                # Vehicle exists → Update location
                if self.db.update_vehicle_location(plate_id, location, location_time):
                    print(f"[P2P] Updated location for {plate_id}: {location}")

                    # Broadcast to frontend (use history_update so frontend reloads)
                    await self._emit_history_update({
                        "type": "history_update",
                        "action": "location_updated",
                        "plate_id": plate_id,
                        "location": location,
                        "location_time": location_time,
                        "event_type": "LOCATION_UPDATE",
                    })

                    # Broadcast to Edges
                    await self._broadcast_to_edges({
                        "type": "LOCATION_UPDATE",
                        "event_id": event_id,
                        "data": {
                            "plate_id": plate_id,
                            "location": location,
                            "location_time": location_time
                        }
                    })
                else:
                    print(f"[P2P] Failed to update location for {plate_id}")
            else:
                # Vehicle not found → Auto-create entry (anomaly)
                entry_id = self.db.create_entry_from_parking_lot(
                    event_id=event_id,
                    source_central=source_central,
                    edge_id=data.get("edge_id", "unknown"),
                    plate_id=plate_id,
                    plate_view=plate_id,  # Use plate_id as display if no plate_view
                    entry_time=location_time,
                    camera_name=f"{source_central}/{location}",
                    location=location,
                    location_time=location_time
                )
                if entry_id:
                    print(f"⚠️ [P2P] Auto-created entry for {plate_id} (ANOMALY)")

                    # Broadcast to frontend (use history_update so frontend reloads)
                    await self._emit_history_update({
                        "type": "history_update",
                        "action": "entry_created",
                        "plate_id": plate_id,
                        "is_anomaly": True,
                        "event_type": "ENTRY",
                    })

                    # Broadcast to Edges
                    await self._broadcast_to_edges({
                        "type": "ENTRY",
                        "event_id": event_id,
                        "data": {
                            "plate_id": plate_id,
                            "is_anomaly": True,
                            "location": location,
                            "location_time": location_time
                        }
                    })

        except Exception as e:
            print(f"Error handling LOCATION_UPDATE: {e}")
            import traceback
            traceback.print_exc()

    async def handle_parking_lot_config(self, message):
        """
        Handle PARKING_LOT_CONFIG from P2P peer (parking lot config update)

        Lưu parking lot config vào database và broadcast đến frontend
        """
        try:
            print(f"[P2P DEBUG] handle_parking_lot_config called, message type: {type(message)}")
            print(f"[P2P DEBUG] message content: {message}")

            # Extract data from P2PMessage or dict
            if hasattr(message, 'source_central'):
                source_central = message.source_central
                data = message.data if hasattr(message, 'data') else {}
            else:
                source_central = message.get("source_central")
                data = message.get("data", {})

            location_name = data.get("location_name")
            capacity = data.get("capacity", 0)
            camera_id = data.get("camera_id")
            camera_type = data.get("camera_type", "PARKING_LOT")
            edge_id = data.get("edge_id")

            print(f"[P2P] Received PARKING_LOT_CONFIG from {source_central}: {location_name}, capacity={capacity}")

            # Save to local database
            if self.db:
                self.db.save_parking_lot_config(
                    location_name=location_name,
                    capacity=capacity,
                    camera_id=camera_id,
                    camera_type=camera_type,
                    edge_id=edge_id
                )
                print(f"[P2P] Saved parking lot config: {location_name}, capacity={capacity}")

                # Broadcast to frontend via WebSocket
                await self._emit_history_update({
                    "event_type": "PARKING_LOT_CONFIG_UPDATE",
                    "camera_name": location_name,
                    "capacity": capacity
                })

        except Exception as e:
            print(f"Error handling PARKING_LOT_CONFIG: {e}")
            import traceback
            traceback.print_exc()

    async def _emit_history_update(self, payload: dict):
        """Gửi tín hiệu history_update cho WebSocket UI khi có sync từ P2P."""
        if not self.on_history_update:
            return
        try:
            asyncio.create_task(self.on_history_update(payload))
        except Exception as e:
            print(f"Error emitting history update: {e}")

    async def _broadcast_to_edges(self, event: dict):
        """Broadcast event to all connected Edge backends"""
        if not self.on_edge_broadcast:
            return
        try:
            await self.on_edge_broadcast(event)
        except Exception as e:
            print(f"Error broadcasting to edges: {e}")
            traceback.print_exc()

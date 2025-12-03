"""
P2P Event Handler - Xử lý events nhận từ peer centrals
"""
from typing import Optional
from datetime import datetime
import traceback

from .protocol import P2PMessage, MessageType


class P2PEventHandler:
    """Handler cho P2P events"""

    def __init__(self, database, this_central_id: str):
        self.db = database
        self.this_central_id = this_central_id

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

            # Check duplicate - nếu đã có event_id này rồi thì skip
            if self._event_exists(event_id):
                print(f"⚠️ Event {event_id} already exists, skipping")
                return

            # Check conflict - nếu xe này đã vào từ central khác
            existing = self.db.find_vehicle_in_parking(plate_id)
            if existing:
                # Conflict detected - so sánh timestamp
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
                camera_id=None,  # Edge camera, không có camera_id của central
                camera_name=f"{source_central}/{edge_id}",
                confidence=0.0,  # Unknown từ remote
                source="p2p_sync"
            )

            print(f"✅ Synced ENTRY from {source_central}: {plate_view} ({event_id})")

        except Exception as e:
            print(f"❌ Error handling VEHICLE_ENTRY_PENDING: {e}")
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
            # (Trong design hiện tại, PENDING và CONFIRMED đều là status='IN')
            # Nếu cần phân biệt, có thể thêm column 'barrier_status'

            # Hiện tại chỉ log
            print(f"✅ Entry {event_id} confirmed at {confirmed_time}")

        except Exception as e:
            print(f"❌ Error handling VEHICLE_ENTRY_CONFIRMED: {e}")
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

            # Update exit info
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
                print(f"✅ Synced EXIT from {exit_central}: event {event_id}, fee {fee}")
            else:
                print(f"⚠️ Failed to update exit for event {event_id} - entry not found")

        except Exception as e:
            print(f"❌ Error handling VEHICLE_EXIT: {e}")
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
                # Entry cũ không có event_id (tạo trước khi có P2P)
                # Giữ entry cũ
                print(f"⚠️ Conflict: Keeping old entry (no event_id)")
                return

            # Parse timestamp từ event_id (format: central-1_timestamp_plate_id)
            existing_timestamp = self._parse_timestamp_from_event_id(existing_event_id)
            new_timestamp = self._parse_timestamp_from_event_id(new_event_id)

            if existing_timestamp is None or new_timestamp is None:
                print(f"⚠️ Cannot parse timestamp, keeping existing entry")
                return

            if new_timestamp < existing_timestamp:
                # Event mới CŨ HƠN → xóa entry hiện tại, insert entry mới
                print(f"🔄 Conflict: New entry is older, replacing local entry")
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

                print(f"✅ Replaced with older entry from {new_message.source_central}")

            else:
                # Entry hiện tại CŨ HƠN → giữ nguyên, ignore message mới
                print(f"⚠️ Conflict: Local entry is older, ignoring new entry")
                print(f"   Local: {existing_event_id} (ts={existing_timestamp})")
                print(f"   Remote: {new_event_id} (ts={new_timestamp})")

        except Exception as e:
            print(f"❌ Error resolving conflict: {e}")
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

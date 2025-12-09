"""
P2P Sync Manager - Handle sync on reconnect

Khi peer reconnect sau khi offline:
1. Track last_sync_time với mỗi peer
2. Send SYNC_REQUEST với since_timestamp
3. Peer gửi lại SYNC_RESPONSE với missed events
4. Merge events vào local DB
"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime

from .protocol import (
    P2PMessage,
    MessageType,
    create_sync_request_message,
    create_sync_response_message
)


class P2PSyncManager:
    """Manager cho sync logic"""

    def __init__(self, database, p2p_manager, central_id: str):
        self.db = database
        self.p2p_manager = p2p_manager
        self.central_id = central_id

    def get_last_sync_timestamp(self, peer_id: str) -> int:
        """
        Get last sync timestamp với peer

        Returns:
            Timestamp in milliseconds, hoặc 0 nếu chưa từng sync
        """
        try:
            with self.db.lock:
                conn = sqlite3.connect(self.db.db_file)
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT last_sync_timestamp FROM p2p_sync_state WHERE peer_central_id = ?",
                    (peer_id,)
                )

                result = cursor.fetchone()
                conn.close()

                if result:
                    return result[0]
                else:
                    # Chua co record → lan dau sync
                    # Return timestamp 7 days ago (sync 7 ngay gan nhat)
                    from datetime import timedelta
                    week_ago = datetime.now() - timedelta(days=7)
                    return int(week_ago.timestamp() * 1000)

        except Exception as e:
            print(f"Error getting last sync timestamp: {e}")
            return 0

    def update_last_sync_timestamp(self, peer_id: str, timestamp_ms: int):
        """Update last sync timestamp với peer"""
        try:
            with self.db.lock:
                conn = sqlite3.connect(self.db.db_file)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO p2p_sync_state (peer_central_id, last_sync_timestamp, last_sync_time, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(peer_central_id) DO UPDATE SET
                        last_sync_timestamp = excluded.last_sync_timestamp,
                        last_sync_time = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (peer_id, timestamp_ms)
                )

                conn.commit()
                conn.close()

                print(f"Updated last sync timestamp for {peer_id}: {timestamp_ms}")

        except Exception as e:
            print(f"Error updating last sync timestamp: {e}")

    async def request_sync_from_peer(self, peer_id: str):
        """
        Request sync từ peer khi reconnect

        Flow:
        1. Get last_sync_timestamp
        2. Send SYNC_REQUEST
        3. Peer sẽ respond với SYNC_RESPONSE
        """
        try:
            last_sync = self.get_last_sync_timestamp(peer_id)

            print(f"Requesting sync from {peer_id} (since {last_sync})")

            message = create_sync_request_message(
                source_central=self.central_id,
                since_timestamp=last_sync
            )

            success = await self.p2p_manager.send_to_peer(peer_id, message)

            if success:
                print(f"Sent SYNC_REQUEST to {peer_id}")
            else:
                print(f"Failed to send SYNC_REQUEST to {peer_id}")

        except Exception as e:
            print(f"Error requesting sync from {peer_id}: {e}")
            import traceback
            traceback.print_exc()

    async def handle_sync_request(self, message: P2PMessage, from_peer_id: str):
        """
        Handle SYNC_REQUEST từ peer

        Peer hỏi: "Cho tôi tất cả events từ timestamp X"

        Flow:
        1. Get events since timestamp
        2. Convert to serializable format
        3. Send SYNC_RESPONSE
        """
        try:
            since_timestamp = message.data.get("since_timestamp", 0)

            print(f"Received SYNC_REQUEST from {from_peer_id} (since {since_timestamp})")

            # Get events since timestamp
            events = self.db.get_events_since(since_timestamp, limit=5000)

            # Convert events to serializable format
            serialized_events = []
            for event in events:
                # Clean event data (remove None, convert datetime to string, etc.)
                clean_event = {}
                for key, value in event.items():
                    if value is not None:
                        clean_event[key] = value

                serialized_events.append(clean_event)

            print(f"Sending {len(serialized_events)} events to {from_peer_id}")

            # Send SYNC_RESPONSE
            response = create_sync_response_message(
                source_central=self.central_id,
                events=serialized_events
            )

            await self.p2p_manager.send_to_peer(from_peer_id, response)

            print(f"Sent SYNC_RESPONSE to {from_peer_id}")

        except Exception as e:
            print(f"Error handling SYNC_REQUEST: {e}")
            import traceback
            traceback.print_exc()

    async def handle_sync_response(self, message: P2PMessage, from_peer_id: str):
        """
        Handle SYNC_RESPONSE từ peer

        Peer gửi lại danh sách events missed

        Flow:
        1. Parse events
        2. Merge vào local DB (skip duplicates)
        3. Update last_sync_timestamp
        """
        try:
            events = message.data.get("events", [])

            print(f"Received SYNC_RESPONSE from {from_peer_id}: {len(events)} events")

            if not events:
                print(f"No missed events from {from_peer_id}")
                # Update sync timestamp to now
                now_ms = int(datetime.now().timestamp() * 1000)
                self.update_last_sync_timestamp(from_peer_id, now_ms)
                return

            # Merge events
            merged_count = 0
            skipped_count = 0

            for event in events:
                event_id = event.get("event_id")

                if not event_id:
                    # Old event without event_id, skip
                    skipped_count += 1
                    continue

                # Check if already exists
                if self.db.event_exists(event_id):
                    skipped_count += 1
                    continue

                # Insert event
                try:
                    # Determine if it's entry or exit based on status
                    status = event.get("status", "IN")

                    if status == "IN" or not event.get("exit_time"):
                        # Entry event
                        self.db.add_vehicle_entry_p2p(
                            event_id=event_id,
                            source_central=event.get("source_central", from_peer_id),
                            edge_id=event.get("edge_id", "unknown"),
                            plate_id=event.get("plate_id"),
                            plate_view=event.get("plate_view", event.get("plate_id")),
                            entry_time=event.get("entry_time"),
                            camera_id=event.get("entry_camera_id"),
                            camera_name=event.get("entry_camera_name", "unknown"),
                            confidence=event.get("entry_confidence", 0.0),
                            source="sync"
                        )
                        merged_count += 1

                    if status == "OUT" and event.get("exit_time"):
                        # Has exit info, update
                        self.db.update_vehicle_exit_p2p(
                            event_id=event_id,
                            exit_time=event.get("exit_time"),
                            camera_id=event.get("exit_camera_id"),
                            camera_name=event.get("exit_camera_name", "unknown"),
                            confidence=event.get("exit_confidence", 0.0),
                            source="sync",
                            duration=event.get("duration", ""),
                            fee=event.get("fee", 0)
                        )

                except Exception as e:
                    print(f"Error merging event {event_id}: {e}")
                    skipped_count += 1
                    continue

            print(f"Merged {merged_count} events, skipped {skipped_count}")

            # Update last sync timestamp to now
            now_ms = int(datetime.now().timestamp() * 1000)
            self.update_last_sync_timestamp(from_peer_id, now_ms)

        except Exception as e:
            print(f"Error handling SYNC_RESPONSE: {e}")
            import traceback
            traceback.print_exc()

    async def on_peer_connected(self, peer_id: str):
        """
        Callback khi peer connected

        Automatically request sync
        """
        print(f"Peer {peer_id} connected, requesting sync...")
        await self.request_sync_from_peer(peer_id)

    async def on_peer_disconnected(self, peer_id: str):
        """
        Callback khi peer disconnected

        Update last known timestamp
        """
        # Update last sync timestamp to now (de lan sau chi sync tu thoi diem nay)
        now_ms = int(datetime.now().timestamp() * 1000)
        self.update_last_sync_timestamp(peer_id, now_ms)
        print(f"Peer {peer_id} disconnected, saved sync timestamp")

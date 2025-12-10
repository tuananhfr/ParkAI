"""
Central Sync Service - Gửi events từ Edge lên Central Server
Dùng WebSocket cho real-time sync, fallback to HTTP nếu WebSocket fail
"""
import requests
import threading
import time
from queue import Queue
from typing import Dict, Any, Optional
import uuid
import json
import websocket  # websocket-client library


class CentralSyncService:
    """Service sync events lên central server"""

    def __init__(self, central_url: str, camera_id: int, camera_name: str, camera_type: str, parking_manager=None):
        self.central_url = central_url
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.camera_type = camera_type
        self.parking_manager = parking_manager  # For saving incoming events to local DB

        self.event_queue = Queue()
        self.running = False
        self.sync_thread = None

        # WebSocket
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_connected = False
        self.ws_thread = None

        # Stats
        self.events_sent = 0
        self.events_failed = 0
        self.last_sync_time = None

    def start(self):
        """Start sync service"""
        if self.running:
            return

        self.running = True

        # Start WebSocket connection thread
        self.ws_thread = threading.Thread(target=self._websocket_loop, daemon=True)
        self.ws_thread.start()

        # Start sync thread (for sending events)
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()

        # Send heartbeat every 30s
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()


    def stop(self):
        """Stop sync service"""
        self.running = False
        if self.ws:
            self.ws.close()
        if self.sync_thread:
            self.sync_thread.join(timeout=2)

    def send_event(self, event_type: str, data: Dict[str, Any]):
        """
        Queue event để gửi lên central

        Args:
            event_type: "ENTRY" | "EXIT" | "DETECTION"
            data: Event data (plate_text, timestamp, confidence, etc.)
                  Nếu data có event_id sẵn thì dùng, nếu không thì tạo mới
        """
        plate_id = data.get("plate_id") or data.get("plate_text") or "UNKNOWN"

        # Dùng event_id có sẵn nếu có, nếu không thì tạo mới
        event_id = data.get("event_id")
        if not event_id:
            event_id = self._generate_event_id(plate_id)

        event = {
            "type": event_type,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "camera_type": self.camera_type,
            "timestamp": time.time(),
            "event_id": event_id,
            "data": {
                **data,
                "plate_id": plate_id,
            },
        }
        self.event_queue.put(event)

    def _websocket_loop(self):
        """WebSocket connection loop with auto-reconnect"""
        while self.running:
            try:
                # Build WebSocket URL from HTTP URL
                ws_url = self.central_url.replace("http://", "ws://").replace("https://", "wss://")
                ws_url = f"{ws_url}/ws/edge"

                print(f"[Edge Sync] Connecting to Central WebSocket: {ws_url}")

                # Create WebSocket connection
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close
                )

                # Run forever (blocking until connection closes)
                self.ws.run_forever()

                # Connection closed - wait before reconnect
                print("[Edge Sync] WebSocket disconnected, reconnecting in 5s...")
                time.sleep(5)

            except Exception as e:
                print(f"[Edge Sync] WebSocket error: {e}")
                time.sleep(5)

    def _on_ws_open(self, ws):
        """WebSocket connection opened"""
        print(f"[Edge Sync] WebSocket connected to Central")
        self.ws_connected = True

        # Send identification message
        try:
            ws.send(json.dumps({
                "edge_id": self.camera_id
            }))
        except Exception as e:
            print(f"[Edge Sync] Failed to send identification: {e}")

    def _on_ws_message(self, ws, message):
        """Received message from Central via WebSocket"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "connected":
                print(f"[Edge Sync] {data.get('message')}")

            elif msg_type == "pong":
                # Pong response
                pass

            elif msg_type in ["ENTRY", "EXIT", "DETECTION", "UPDATE", "DELETE"]:
                # Event from Central (from other nodes) - save to local DB
                self._handle_incoming_event(data)

            else:
                print(f"[Edge Sync] Unknown message type: {msg_type}")

        except Exception as e:
            print(f"[Edge Sync] Error handling WebSocket message: {e}")
            import traceback
            traceback.print_exc()

    def _on_ws_error(self, ws, error):
        """WebSocket error"""
        print(f"[Edge Sync] WebSocket error: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        print(f"[Edge Sync] WebSocket closed (code={close_status_code}, msg={close_msg})")
        self.ws_connected = False

    def _handle_incoming_event(self, event: Dict[str, Any]):
        """
        Handle event received from Central (from other nodes)
        Save to local database for sync
        """
        try:
            if not self.parking_manager:
                print("[Edge Sync] No parking_manager, cannot save incoming event")
                return

            event_id = event.get("event_id")
            event_type = event.get("type")
            data = event.get("data", {})

            print(f"[Edge Sync] Received {event_type} event from Central: {event_id}")

            # Check if event already exists (dedupe)
            if self.parking_manager.event_exists(event_id):
                print(f"[Edge Sync] Event {event_id} already exists, skipping")
                return

            # Save to local DB based on event type
            if event_type == "ENTRY":
                self.parking_manager.add_entry_from_sync(
                    event_id=event_id,
                    plate_id=data.get("plate_text", "UNKNOWN"),
                    plate_view=data.get("plate_view", ""),
                    entry_time=event.get("entry_time"),
                    source="central_sync"
                )
                print(f"[Edge Sync] Saved ENTRY to local DB: {event_id}")

            elif event_type == "EXIT":
                self.parking_manager.update_exit_from_sync(
                    event_id=event_id,
                    exit_time=event.get("exit_time"),
                    fee=event.get("fee", 0),
                    duration=event.get("duration", ""),
                    source="central_sync"
                )
                print(f"[Edge Sync] Updated EXIT in local DB: {event_id}")

            elif event_type == "UPDATE":
                # Admin updated record from Central
                history_id = event.get("history_id")
                new_plate_text = data.get("plate_text", "")
                new_plate_view = data.get("plate_view", "")

                if self.parking_manager.db.update_history_entry(history_id, new_plate_text, new_plate_view):
                    print(f"[Edge Sync] Updated record {history_id} in local DB")
                else:
                    print(f"[Edge Sync] Failed to update record {history_id}")

            elif event_type == "DELETE":
                # Admin deleted record from Central
                history_id = event.get("history_id")

                if self.parking_manager.db.delete_history_entry(history_id):
                    print(f"[Edge Sync] Deleted record {history_id} from local DB")
                else:
                    print(f"[Edge Sync] Failed to delete record {history_id}")

        except Exception as e:
            print(f"[Edge Sync] Error handling incoming event: {e}")
            import traceback
            traceback.print_exc()

    def _sync_loop(self):
        """Loop gửi events lên central"""
        while self.running:
            try:
                # Get event from queue (block voi timeout)
                event = self.event_queue.get(timeout=1.0)

                # Send to central
                success = self._send_to_central(event)

                if success:
                    self.events_sent += 1
                    self.last_sync_time = time.time()
                else:
                    self.events_failed += 1
                    # Requeue with slight delay for retry
                    time.sleep(1.0)
                    self.event_queue.put(event)

            except Exception as e:
                # Queue empty - continue
                continue

    def _send_to_central(self, event: Dict[str, Any]) -> bool:
        """
        Send event to central server
        Prefer WebSocket, fallback to HTTP POST
        """
        # Try WebSocket first if connected
        if self.ws_connected and self.ws:
            try:
                self.ws.send(json.dumps(event))
                return True
            except Exception as e:
                print(f"[Edge Sync] WebSocket send failed, falling back to HTTP: {e}")
                # Fall through to HTTP

        # Fallback to HTTP POST
        try:
            response = requests.post(
                f"{self.central_url}/api/edge/event",
                json=event,
                timeout=5.0
            )

            if response.status_code == 200:
                return True
            else:
                print(f"Central sync failed: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            print(f"Central sync error: {e}")
            return False

    def _generate_event_id(self, plate_id: str) -> str:
        """
        Generate stable-ish event_id để central dedupe:
        edge-{camera_id}_{ms_timestamp}_{plate_id}
        """
        ms = int(time.time() * 1000)
        clean_plate = str(plate_id).replace(" ", "").upper()
        return f"edge-{self.camera_id}_{ms}_{clean_plate}"

    def _heartbeat_loop(self):
        """Send heartbeat every 30s"""
        while self.running:
            try:
                self._send_heartbeat()
                time.sleep(30)
            except Exception as e:
                print(f"Heartbeat error: {e}")

    def _send_heartbeat(self):
        """Send heartbeat to central"""
        try:
            response = requests.post(
                f"{self.central_url}/api/edge/heartbeat",
                json={
                    "camera_id": self.camera_id,
                    "camera_name": self.camera_name,
                    "camera_type": self.camera_type,
                    "status": "online",
                    "events_sent": self.events_sent,
                    "events_failed": self.events_failed,
                    "timestamp": time.time()
                },
                timeout=5.0
            )

            if response.status_code != 200:
                print(f" Heartbeat failed: {response.status_code}")

        except requests.RequestException as e:
            print(f" Heartbeat error: {e}")

    def get_status(self):
        """Get sync status"""
        return {
            "running": self.running,
            "central_url": self.central_url,
            "events_sent": self.events_sent,
            "events_failed": self.events_failed,
            "last_sync_time": self.last_sync_time,
            "queue_size": self.event_queue.qsize()
        }

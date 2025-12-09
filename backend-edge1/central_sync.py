"""
Central Sync Service - Gửi events từ Edge lên Central Server
"""
import requests
import threading
import time
from queue import Queue
from typing import Dict, Any


class CentralSyncService:
    """Service sync events lên central server"""

    def __init__(self, central_url: str, camera_id: int, camera_name: str, camera_type: str):
        self.central_url = central_url
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.camera_type = camera_type

        self.event_queue = Queue()
        self.running = False
        self.sync_thread = None

        # Stats
        self.events_sent = 0
        self.events_failed = 0
        self.last_sync_time = None

    def start(self):
        """Start sync service"""
        if self.running:
            return

        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()

        # Send heartbeat every 30s
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()


    def stop(self):
        """Stop sync service"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=2)

    def send_event(self, event_type: str, data: Dict[str, Any]):
        """
        Queue event để gửi lên central

        Args:
            event_type: "ENTRY" | "EXIT" | "DETECTION"
            data: Event data (plate_text, timestamp, confidence, etc.)
        """
        event = {
            "type": event_type,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "camera_type": self.camera_type,
            "timestamp": time.time(),
            "data": data
        }
        self.event_queue.put(event)

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
                    # TODO: Retry logic hoac save to local DB

            except Exception as e:
                # Queue empty - continue
                continue

    def _send_to_central(self, event: Dict[str, Any]) -> bool:
        """Send event to central server"""
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

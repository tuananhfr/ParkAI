"""
Camera Registry - Theo dõi trạng thái của tất cả Edge cameras
"""
from datetime import datetime, timedelta
import threading
import time


class CameraRegistry:
    """Registry để track trạng thái của N cameras"""

    def __init__(self, database, heartbeat_timeout=60):
        self.db = database
        self.heartbeat_timeout = heartbeat_timeout

        # Thread check camera offline
        self.running = False
        self.check_thread = None

    def start(self):
        """Start monitoring thread"""
        if self.running:
            return

        self.running = True
        self.check_thread = threading.Thread(target=self._check_offline_loop, daemon=True)
        self.check_thread.start()


    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=2)

    def update_heartbeat(self, camera_id, name, camera_type, events_sent, events_failed):
        """Update camera heartbeat"""
        self.db.upsert_camera(
            camera_id=camera_id,
            name=name,
            camera_type=camera_type,
            status="online",
            events_sent=events_sent,
            events_failed=events_failed
        )

    def _check_offline_loop(self):
        """Loop kiểm tra cameras offline"""
        while self.running:
            try:
                self._check_offline_cameras()
                time.sleep(10)  # Check moi 10 giay
            except Exception as e:
                print(f"Camera registry error: {e}")

    def _check_offline_cameras(self):
        """Mark cameras as offline if no heartbeat"""
        cameras = self.db.get_cameras()
        # Database luu UTC, nen dung utcnow()
        timeout_threshold = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout)

        for camera in cameras:
            if camera['last_heartbeat']:
                last_heartbeat = datetime.strptime(camera['last_heartbeat'], '%Y-%m-%d %H:%M:%S')

                if last_heartbeat < timeout_threshold and camera['status'] == 'online':
                    # Mark offline
                    self.db.upsert_camera(
                        camera_id=camera['id'],
                        name=camera['name'],
                        camera_type=camera['type'],
                        status='offline',
                        events_sent=camera['events_sent'],
                        events_failed=camera['events_failed']
                    )

    def get_camera_status(self):
        """Get status of all cameras"""
        cameras = self.db.get_cameras()

        return {
            "total": len(cameras),
            "online": sum(1 for c in cameras if c['status'] == 'online'),
            "offline": sum(1 for c in cameras if c['status'] == 'offline'),
            "cameras": cameras
        }

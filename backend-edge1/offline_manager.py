"""
Offline Manager - Quản lý offline mode và event queue
"""
import sqlite3
import json
import asyncio
import httpx
from datetime import datetime
from typing import Tuple, Optional


class OfflineManager:
    """
    Quản lý offline mode:
    - Queue events khi Central down
    - Retry events khi Central online
    - Health check Central
    """

    def __init__(self, central_url: str, db_file: str = "data/offline_queue.db"):
        self.central_url = central_url
        self.db_file = db_file
        self.is_online = False
        self.retry_worker_running = False
        self._init_db()

    def _init_db(self):
        """Initialize offline queue database"""
        conn = sqlite3.connect(self.db_file)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_retry TEXT,
                error_message TEXT
            )
        """)
        conn.commit()
        conn.close()
        print(f"✅ Offline queue DB initialized: {self.db_file}")

    async def send_event(
        self,
        event_type: str,
        event_data: dict,
        timeout: float = 2.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Gửi event đến Central với fallback

        Args:
            event_type: "ENTRY" or "EXIT"
            event_data: Event data dict
            timeout: Request timeout (seconds)

        Returns:
            (success: bool, error_message: str or None)
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.central_url}/api/edge/event",
                    json={
                        "event": event_type,
                        **event_data
                    }
                )

                if response.status_code == 200:
                    self.is_online = True
                    print(f"✅ Event synced: {event_type} - {event_data.get('plate_id')}")
                    return True, None
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
            # Central DOWN → FALLBACK
            self.is_online = False
            error_msg = f"Central offline: {type(e).__name__}"
            print(f"❌ {error_msg}")

            # Queue event locally
            self._queue_event(event_type, event_data, str(e))

            # Start retry worker nếu chưa chạy
            if not self.retry_worker_running:
                asyncio.create_task(self._retry_worker())

            return False, error_msg

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False, str(e)

    def _queue_event(self, event_type: str, event_data: dict, error: str):
        """Lưu event vào queue để retry sau"""
        conn = sqlite3.connect(self.db_file)
        conn.execute("""
            INSERT INTO pending_events (event_type, event_data, created_at, error_message)
            VALUES (?, ?, ?, ?)
        """, (
            event_type,
            json.dumps(event_data),
            datetime.now().isoformat(),
            error
        ))
        conn.commit()

        # Get queue size
        cursor = conn.execute("SELECT COUNT(*) FROM pending_events")
        queue_size = cursor.fetchone()[0]

        conn.close()
        print(f"📦 Queued event: {event_type} - {event_data.get('plate_id')} (Queue: {queue_size})")

    async def _retry_worker(self):
        """Background worker: Retry pending events mỗi 30s"""
        self.retry_worker_running = True
        print("🔄 Retry worker started...")

        while True:
            try:
                # Check health
                is_healthy = await self._check_central_health()

                if is_healthy and not self.is_online:
                    print("✅ Central is back online!")
                    self.is_online = True

                if is_healthy:
                    # Replay pending events
                    await self._replay_pending_events()

                # Sleep 30s
                await asyncio.sleep(30)

            except Exception as e:
                print(f"❌ Retry worker error: {e}")
                await asyncio.sleep(30)

    async def _check_central_health(self) -> bool:
        """Check if Central is online"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.central_url}/api/health")
                return response.status_code == 200
        except:
            return False

    async def _replay_pending_events(self):
        """Replay tất cả pending events"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.execute("""
            SELECT id, event_type, event_data, retry_count
            FROM pending_events
            ORDER BY created_at ASC
            LIMIT 100
        """)

        events = cursor.fetchall()

        if len(events) == 0:
            conn.close()
            return

        print(f"🔄 Replaying {len(events)} pending events...")

        for event_id, event_type, event_data_json, retry_count in events:
            event_data = json.loads(event_data_json)

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        f"{self.central_url}/api/edge/event",
                        json={"event": event_type, **event_data}
                    )

                    if response.status_code == 200:
                        # Success → Delete
                        conn.execute("DELETE FROM pending_events WHERE id=?", (event_id,))
                        conn.commit()
                        print(f"✅ Replayed: {event_type} - {event_data.get('plate_id')}")
                    else:
                        # Failed → Update retry count
                        conn.execute("""
                            UPDATE pending_events
                            SET retry_count = retry_count + 1,
                                last_retry = ?,
                                error_message = ?
                            WHERE id = ?
                        """, (
                            datetime.now().isoformat(),
                            f"HTTP {response.status_code}",
                            event_id
                        ))
                        conn.commit()
                        print(f"⚠️  Retry failed: {event_type} - {event_data.get('plate_id')}")

            except Exception as e:
                print(f"❌ Replay error: {e}")
                # Update retry count
                conn.execute("""
                    UPDATE pending_events
                    SET retry_count = retry_count + 1,
                        last_retry = ?,
                        error_message = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), str(e), event_id))
                conn.commit()
                break  # Central vẫn down, dừng replay

        conn.close()

    def get_queue_stats(self) -> dict:
        """Get queue statistics"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN retry_count = 0 THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) as retrying,
                MAX(retry_count) as max_retries
            FROM pending_events
        """)
        stats = dict(cursor.fetchone())
        conn.close()
        return {
            "total": stats.get('total', 0) or 0,
            "pending": stats.get('pending', 0) or 0,
            "retrying": stats.get('retrying', 0) or 0,
            "max_retries": stats.get('max_retries', 0) or 0,
            "is_online": self.is_online
        }

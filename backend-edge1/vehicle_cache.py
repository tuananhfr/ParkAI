"""
Vehicle Cache - Local SQLite cache cho Edge (sync từ Central)
"""
import sqlite3
import threading
from datetime import datetime
from typing import Optional, Dict, List


class VehicleCache:
    """
    Local cache for Edge
    - Lưu vehicle state từ WebSocket updates
    - Query nhanh (local SQLite)
    - Thread-safe
    """

    def __init__(self, db_file: str = "data/edge_cache.db"):
        self.db_file = db_file
        self.local = threading.local()  # Thread-safe connections
        self._init_db()

    def _get_conn(self):
        """Get thread-local connection"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

    def _init_db(self):
        """Initialize cache schema"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vehicle_cache (
                plate_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,  -- 'IN' or 'OUT'
                entry_gate INTEGER,
                entry_time TEXT,
                entry_camera_name TEXT,
                exit_gate INTEGER,
                exit_time TEXT,
                exit_camera_name TEXT,
                fee INTEGER DEFAULT 0,
                duration TEXT,
                last_sync TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_status ON vehicle_cache(status);
            CREATE INDEX IF NOT EXISTS idx_last_sync ON vehicle_cache(last_sync DESC);
        """)
        conn.commit()
        print(f"Vehicle cache DB initialized: {self.db_file}")

    def update_from_websocket(
        self,
        event_type: str,
        plate_id: str,
        gate: int,
        **kwargs
    ):
        """
        Update cache từ WebSocket message

        Args:
            event_type: "ENTRY" or "EXIT"
            plate_id: Biển số (cleaned)
            gate: Gate number
            **kwargs: entry_time, exit_time, fee, duration, camera_name, etc.
        """
        conn = self._get_conn()

        if event_type == "ENTRY":
            conn.execute("""
                INSERT OR REPLACE INTO vehicle_cache
                (plate_id, status, entry_gate, entry_time, entry_camera_name, last_sync)
                VALUES (?, 'IN', ?, ?, ?, ?)
            """, (
                plate_id,
                gate,
                kwargs.get('entry_time', datetime.now().isoformat()),
                kwargs.get('camera_name', f'Gate {gate}'),
                datetime.now().isoformat()
            ))
            print(f"📥 Cache updated: {plate_id} IN at Gate {gate}")

        elif event_type == "EXIT":
            conn.execute("""
                UPDATE vehicle_cache
                SET status='OUT',
                    exit_gate=?,
                    exit_time=?,
                    exit_camera_name=?,
                    fee=?,
                    duration=?,
                    last_sync=?
                WHERE plate_id=?
            """, (
                gate,
                kwargs.get('exit_time', datetime.now().isoformat()),
                kwargs.get('camera_name', f'Gate {gate}'),
                kwargs.get('fee', 0),
                kwargs.get('duration', ''),
                datetime.now().isoformat(),
                plate_id
            ))
            print(f"📥 Cache updated: {plate_id} OUT at Gate {gate}")

        conn.commit()

    def check_vehicle_in_parking(self, plate_id: str) -> Optional[Dict]:
        """
        Check if vehicle is IN parking (bất kỳ gate nào)

        Returns:
            dict with vehicle info or None
        """
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT * FROM vehicle_cache
            WHERE plate_id=? AND status='IN'
        """, (plate_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def add_local_entry(
        self,
        plate_id: str,
        gate: int,
        entry_time: str,
        camera_name: str = None
    ):
        """
        Add entry local (khi Edge mở cửa VÀO)

        Args:
            plate_id: Biển số
            gate: Gate number
            entry_time: Entry timestamp
            camera_name: Camera name
        """
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO vehicle_cache
            (plate_id, status, entry_gate, entry_time, entry_camera_name, last_sync)
            VALUES (?, 'IN', ?, ?, ?, ?)
        """, (
            plate_id,
            gate,
            entry_time,
            camera_name or f'Gate {gate}',
            datetime.now().isoformat()
        ))
        conn.commit()
        print(f"Local entry added: {plate_id} at Gate {gate}")

    def update_local_exit(
        self,
        plate_id: str,
        gate: int,
        exit_time: str,
        fee: int,
        duration: str = "",
        camera_name: str = None
    ):
        """
        Update exit local (khi Edge mở cửa RA)

        Args:
            plate_id: Biển số
            gate: Gate number
            exit_time: Exit timestamp
            fee: Parking fee
            duration: Duration string
            camera_name: Camera name
        """
        conn = self._get_conn()
        conn.execute("""
            UPDATE vehicle_cache
            SET status='OUT',
                exit_gate=?,
                exit_time=?,
                exit_camera_name=?,
                fee=?,
                duration=?,
                last_sync=?
            WHERE plate_id=?
        """, (
            gate,
            exit_time,
            camera_name or f'Gate {gate}',
            fee,
            duration,
            datetime.now().isoformat(),
            plate_id
        ))
        conn.commit()
        print(f"Local exit updated: {plate_id} at Gate {gate}, Fee: {fee:,}đ")

    def get_all_in_parking(self) -> List[Dict]:
        """Get all vehicles currently IN parking"""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT * FROM vehicle_cache
            WHERE status='IN'
            ORDER BY entry_time DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_history(self, limit: int = 100) -> List[Dict]:
        """Get recent history"""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT * FROM vehicle_cache
            ORDER BY last_sync DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='IN' THEN 1 ELSE 0 END) as in_parking,
                SUM(CASE WHEN status='OUT' THEN 1 ELSE 0 END) as out,
                MAX(last_sync) as last_sync
            FROM vehicle_cache
        """)
        stats = dict(cursor.fetchone())
        return {
            "total": stats.get('total', 0) or 0,
            "in_parking": stats.get('in_parking', 0) or 0,
            "out": stats.get('out', 0) or 0,
            "last_sync": stats.get('last_sync', '')
        }

    def clear_old_records(self, days: int = 30):
        """Clear records older than N days"""
        conn = self._get_conn()
        cutoff = datetime.now().replace(
            day=datetime.now().day - days
        ).isoformat()

        cursor = conn.execute("""
            DELETE FROM vehicle_cache
            WHERE status='OUT' AND last_sync < ?
        """, (cutoff,))

        deleted = cursor.rowcount
        conn.commit()

        if deleted > 0:
            print(f"🗑️  Cleared {deleted} old records (>{days} days)")

        return deleted

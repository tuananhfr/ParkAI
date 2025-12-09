"""
Database Extensions for P2P - Thêm methods vào CentralDatabase

Để không modify file database.py gốc, ta tạo extension functions
và monkey-patch vào CentralDatabase class
"""
import sqlite3
from threading import Lock


def add_vehicle_entry_p2p(
    self,
    event_id: str,
    source_central: str,
    edge_id: str,
    plate_id: str,
    plate_view: str,
    entry_time: str,
    camera_id: int,
    camera_name: str,
    confidence: float,
    source: str
):
    """
    Add vehicle entry từ P2P sync

    Similar to add_vehicle_entry nhưng có thêm P2P fields
    """
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO history (
                    event_id, source_central, edge_id,
                    plate_id, plate_view, entry_time,
                    entry_camera_id, entry_camera_name,
                    entry_confidence, entry_source,
                    status, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN', 'SYNCED')
                """,
                (
                    event_id, source_central, edge_id,
                    plate_id, plate_view, entry_time,
                    camera_id, camera_name,
                    confidence, source
                ),
            )

            history_id = cursor.lastrowid
            conn.commit()
            return history_id

        except Exception as e:
            conn.rollback()
            print(f"Error adding P2P vehicle entry: {e}")
            raise
        finally:
            conn.close()


def update_vehicle_exit_p2p(
    self,
    event_id: str,
    exit_time: str,
    camera_id: int,
    camera_name: str,
    confidence: float,
    source: str,
    duration: str,
    fee: int
):
    """
    Update vehicle exit từ P2P sync

    Tìm entry theo event_id thay vì plate_id
    """
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE history
            SET exit_time = ?, exit_camera_id = ?, exit_camera_name = ?,
                exit_confidence = ?, exit_source = ?, duration = ?, fee = ?,
                status = 'OUT', updated_at = CURRENT_TIMESTAMP
            WHERE event_id = ? AND status = 'IN'
            """,
            (exit_time, camera_id, camera_name, confidence, source, duration, fee, event_id),
        )

        rows_updated = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_updated > 0


def event_exists(self, event_id: str) -> bool:
    """Check if event_id already exists"""
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM history WHERE event_id = ? LIMIT 1",
            (event_id,)
        )

        result = cursor.fetchone()
        conn.close()

        return result is not None


def delete_entry_by_event_id(self, event_id: str) -> bool:
    """Delete entry by event_id (dùng cho conflict resolution)"""
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM history WHERE event_id = ?",
                (event_id,)
            )

            rows_deleted = cursor.rowcount
            conn.commit()
            return rows_deleted > 0

        except Exception as e:
            conn.rollback()
            print(f"Error deleting entry by event_id: {e}")
            return False

        finally:
            conn.close()


def get_events_since(self, timestamp_ms: int, limit: int = 1000):
    """
    Get all events since timestamp (for sync)

    Args:
        timestamp_ms: Timestamp in milliseconds
        limit: Max events to return

    Returns:
        List of event dicts
    """
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Convert timestamp ms to datetime string
        from datetime import datetime
        timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            """
            SELECT * FROM history
            WHERE created_at >= ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (timestamp_dt, limit)
        )

        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]


def get_sync_state(self):
    """Get sync state với tất cả peers"""
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM p2p_sync_state ORDER BY peer_central_id"
        )

        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]


def init_p2p_tables(database_instance):
    """Initialize P2P tables if they don't exist"""
    with database_instance.lock:
        conn = sqlite3.connect(database_instance.db_file)
        cursor = conn.cursor()

        # Create p2p_sync_state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS p2p_sync_state (
                peer_central_id TEXT PRIMARY KEY,
                last_sync_timestamp INTEGER NOT NULL,
                last_sync_time TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()
        print("P2P tables initialized")


def patch_database_for_p2p(database_instance):
    """
    Monkey-patch CentralDatabase instance với P2P methods

    Usage:
        database = CentralDatabase()
        patch_database_for_p2p(database)
        # Now database has P2P methods
    """
    # First, initialize P2P tables
    init_p2p_tables(database_instance)

    # Then patch methods
    database_instance.add_vehicle_entry_p2p = add_vehicle_entry_p2p.__get__(database_instance)
    database_instance.update_vehicle_exit_p2p = update_vehicle_exit_p2p.__get__(database_instance)
    database_instance.event_exists = event_exists.__get__(database_instance)
    database_instance.delete_entry_by_event_id = delete_entry_by_event_id.__get__(database_instance)
    database_instance.get_events_since = get_events_since.__get__(database_instance)
    database_instance.get_sync_state = get_sync_state.__get__(database_instance)

    print("Database patched with P2P methods")

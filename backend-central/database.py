"""
Central Database - Tổng hợp data từ tất cả cameras
"""
import sqlite3
import os
from threading import Lock
from datetime import datetime


class CentralDatabase:
    """Central database để tổng hợp data từ Edge servers"""

    def __init__(self, db_file="data/central.db"):
        self.db_file = db_file
        self.lock = Lock()

        # Create directory if not exists
        os.makedirs(os.path.dirname(db_file), exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database tables"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Table: vehicles (trạng thái xe trong bãi)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_id TEXT NOT NULL UNIQUE,
                    plate_view TEXT NOT NULL,

                    entry_time TEXT NOT NULL,
                    entry_camera_id INTEGER,
                    entry_camera_name TEXT,
                    entry_confidence REAL,
                    entry_source TEXT,

                    exit_time TEXT,
                    exit_camera_id INTEGER,
                    exit_camera_name TEXT,
                    exit_confidence REAL,
                    exit_source TEXT,

                    duration TEXT,
                    fee INTEGER DEFAULT 0,
                    status TEXT NOT NULL,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table: events (log tất cả events từ Edge)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    camera_id INTEGER NOT NULL,
                    camera_name TEXT,
                    camera_type TEXT,
                    plate_text TEXT,
                    confidence REAL,
                    source TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    data TEXT
                )
            """)

            # Table: cameras (registry của tất cả cameras)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT DEFAULT 'offline',
                    last_heartbeat TEXT,
                    events_sent INTEGER DEFAULT 0,
                    events_failed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()

    def add_vehicle_entry(self, plate_id, plate_view, entry_time, camera_id, camera_name, confidence, source):
        """Add vehicle entry"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO vehicles (
                        plate_id, plate_view, entry_time, entry_camera_id, entry_camera_name,
                        entry_confidence, entry_source, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'IN')
                """, (plate_id, plate_view, entry_time, camera_id, camera_name, confidence, source))

                vehicle_id = cursor.lastrowid
                conn.commit()
                return vehicle_id
            except sqlite3.IntegrityError as e:
                # UNIQUE constraint violation - xe đã tồn tại
                # Kiểm tra xem xe có đang trong bãi không
                cursor.execute("""
                    SELECT id, status FROM vehicles WHERE plate_id = ?
                """, (plate_id,))
                existing = cursor.fetchone()
                conn.rollback()
                if existing and existing[1] == 'IN':
                    # Xe đang trong bãi - không cho vào lại
                    raise Exception(f"Xe {plate_view} đã VÀO lúc trước đó")
                else:
                    # Xe đã ra - cho phép vào lại bằng cách UPDATE
                    cursor.execute("""
                        UPDATE vehicles SET
                            plate_view = ?,
                            entry_time = ?,
                            entry_camera_id = ?,
                            entry_camera_name = ?,
                            entry_confidence = ?,
                            entry_source = ?,
                            exit_time = NULL,
                            exit_camera_id = NULL,
                            exit_camera_name = NULL,
                            exit_confidence = NULL,
                            exit_source = NULL,
                            duration = NULL,
                            fee = 0,
                            status = 'IN',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE plate_id = ?
                    """, (plate_view, entry_time, camera_id, camera_name, confidence, source, plate_id))
                    conn.commit()
                    return existing[0] if existing else None
            except Exception as e:
                conn.rollback()
                print(f"❌ Error adding vehicle entry: {e}")
                raise
            finally:
                conn.close()

    def update_vehicle_exit(self, plate_id, exit_time, camera_id, camera_name, confidence, source, duration, fee):
        """Update vehicle exit"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE vehicles
                SET exit_time = ?, exit_camera_id = ?, exit_camera_name = ?,
                    exit_confidence = ?, exit_source = ?, duration = ?, fee = ?,
                    status = 'OUT', updated_at = CURRENT_TIMESTAMP
                WHERE plate_id = ? AND status = 'IN'
            """, (exit_time, camera_id, camera_name, confidence, source, duration, fee, plate_id))

            rows_updated = cursor.rowcount
            conn.commit()
            conn.close()

            return rows_updated > 0

    def find_vehicle_in_parking(self, plate_id):
        """Find vehicle currently IN parking"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM vehicles
                WHERE plate_id = ? AND status = 'IN'
                ORDER BY created_at DESC
                LIMIT 1
            """, (plate_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                return dict(result)
            return None

    def add_event(self, event_type, camera_id, camera_name, camera_type, plate_text, confidence, source, data):
        """Log event from Edge"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            import json
            cursor.execute("""
                INSERT INTO events (
                    event_type, camera_id, camera_name, camera_type,
                    plate_text, confidence, source, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_type, camera_id, camera_name, camera_type, plate_text, confidence, source, json.dumps(data)))

            conn.commit()
            conn.close()

    def upsert_camera(self, camera_id, name, camera_type, status, events_sent, events_failed):
        """Update or insert camera info"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO cameras (id, name, type, status, last_heartbeat, events_sent, events_failed, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    status = excluded.status,
                    last_heartbeat = CURRENT_TIMESTAMP,
                    events_sent = excluded.events_sent,
                    events_failed = excluded.events_failed,
                    updated_at = CURRENT_TIMESTAMP
            """, (camera_id, name, camera_type, status, events_sent, events_failed))

            conn.commit()
            conn.close()

    def get_cameras(self):
        """Get all cameras"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM cameras ORDER BY id")
            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]

    def get_vehicles_in_parking(self):
        """Get vehicles currently IN parking"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM vehicles
                WHERE status = 'IN'
                ORDER BY entry_time DESC
            """)

            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]

    def get_history(self, limit=100, offset=0, today_only=False, status=None, search=None):
        """Get vehicle history with optional search"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM vehicles WHERE 1=1"
            params = []

            if today_only:
                query += " AND DATE(created_at) = DATE('now')"

            if status:
                query += " AND status = ?"
                params.append(status)

            if search:
                # Search in both plate_id and plate_view (normalized search)
                # Remove spaces, dots, dashes for flexible search
                normalized_search = search.upper().replace(" ", "").replace("-", "").replace(".", "")
                query += """ AND (
                    REPLACE(REPLACE(REPLACE(UPPER(plate_id), ' ', ''), '-', ''), '.', '') LIKE ?
                    OR REPLACE(REPLACE(REPLACE(UPPER(plate_view), ' ', ''), '-', ''), '.', '') LIKE ?
                )"""
                search_pattern = f"%{normalized_search}%"
                params.append(search_pattern)
                params.append(search_pattern)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]

    def get_stats(self):
        """Get parking statistics"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Vehicles in parking
            cursor.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'IN'")
            vehicles_in = cursor.fetchone()[0]

            # Total entries today
            cursor.execute("SELECT COUNT(*) FROM vehicles WHERE DATE(created_at) = DATE('now')")
            entries_today = cursor.fetchone()[0]

            # Total exits today
            cursor.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'OUT' AND DATE(updated_at) = DATE('now')")
            exits_today = cursor.fetchone()[0]

            # Total revenue today
            cursor.execute("SELECT SUM(fee) FROM vehicles WHERE status = 'OUT' AND DATE(updated_at) = DATE('now')")
            revenue = cursor.fetchone()[0] or 0

            conn.close()

            return {
                "vehicles_in_parking": vehicles_in,
                "entries_today": entries_today,
                "exits_today": exits_today,
                "revenue_today": revenue
            }

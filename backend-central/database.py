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

            # Table: history (luu TOAN BO lich su vao/ra - KHONG CO UNIQUE CONSTRAINT)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT,
                    source_central TEXT,
                    edge_id TEXT,
                    plate_id TEXT NOT NULL,
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
                    sync_status TEXT DEFAULT 'LOCAL',

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index cho history table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_plate_id
                ON history(plate_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_status
                ON history(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_created_at
                ON history(created_at)
            """)

            # Ensure backward-compatible columns for existing DBs
            self._ensure_history_columns(conn, cursor)

            # Table: events (log tat ca events tu Edge)
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

            # Table: cameras (registry cua tat ca cameras)
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

            # Table: history_changes (luu lich su thay doi bien so)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    history_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,  -- 'UPDATE' hoặc 'DELETE'
                    old_plate_id TEXT,
                    old_plate_view TEXT,
                    new_plate_id TEXT,
                    new_plate_view TEXT,
                    old_data TEXT,  -- JSON của toàn bộ record cũ
                    new_data TEXT,  -- JSON của toàn bộ record mới (nếu UPDATE)
                    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    changed_by TEXT DEFAULT 'system'
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_changes_history_id
                ON history_changes(history_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_changes_changed_at
                ON history_changes(changed_at DESC)
            """)

            # Table: parking_lots - Store parking lot configurations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parking_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_name TEXT NOT NULL UNIQUE,   -- Camera name (e.g., "Bãi A")
                    capacity INTEGER DEFAULT 0,            -- Total parking spots
                    camera_id INTEGER,                     -- Camera ID that manages this lot
                    camera_type TEXT,                      -- Should be "PARKING_LOT"
                    edge_id TEXT,                          -- Which edge this parking lot belongs to
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parking_lots_location
                ON parking_lots(location_name)
            """)

            conn.commit()
            conn.close()

    def _ensure_history_columns(self, conn, cursor):
        """
        Add missing columns to history for backward compatibility.
        Columns required by P2P/sync flows: event_id, source_central, edge_id, sync_status.
        """
        cursor.execute("PRAGMA table_info(history)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        def add_col(name, ddl):
            if name not in existing_cols:
                cursor.execute(f"ALTER TABLE history ADD COLUMN {name} {ddl}")

        add_col("event_id", "TEXT")
        add_col("source_central", "TEXT")
        add_col("edge_id", "TEXT")
        add_col("sync_status", "TEXT DEFAULT 'LOCAL'")
        # Location tracking columns for PARKING_LOT camera
        add_col("last_location", "TEXT")
        add_col("last_location_time", "TEXT")
        add_col("is_anomaly", "INTEGER DEFAULT 0")

    def add_vehicle_entry(
        self,
        plate_id,
        plate_view,
        entry_time,
        camera_id,
        camera_name,
        confidence,
        source,
        event_id=None,
        source_central=None,
        edge_id=None,
        sync_status="LOCAL",
    ):
        """
        Add vehicle entry - Giờ CHỈ lưu vào bảng history.

        Trả về history_id của bản ghi vừa tạo.
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO history (
                        event_id, source_central, edge_id,
                        plate_id, plate_view, entry_time, entry_camera_id, entry_camera_name,
                        entry_confidence, entry_source, status, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN', ?)
                    """,
                    (
                        event_id,
                        source_central,
                        edge_id,
                        plate_id,
                        plate_view,
                        entry_time,
                        camera_id,
                        camera_name,
                        confidence,
                        source,
                        sync_status,
                    ),
                )

                history_id = cursor.lastrowid
                conn.commit()
                return history_id
            except Exception as e:
                conn.rollback()
                print(f"Error adding vehicle entry: {e}")
                raise
            finally:
                conn.close()

    def update_vehicle_exit(self, plate_id, exit_time, camera_id, camera_name, confidence, source, duration, fee):
        """
        Update vehicle exit - Giờ CHỈ cập nhật bản ghi tương ứng trong history.

        Trả về True nếu có bản ghi được cập nhật, ngược lại False.
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
                WHERE id = (
                    SELECT id FROM history
                    WHERE plate_id = ? AND status = 'IN' AND exit_time IS NULL
                    ORDER BY entry_time DESC, created_at DESC
                    LIMIT 1
                )
                """,
                (exit_time, camera_id, camera_name, confidence, source, duration, fee, plate_id),
            )

            rows_updated = cursor.rowcount

            conn.commit()
            conn.close()

            return rows_updated > 0

    def find_vehicle_in_parking(self, plate_id):
        """
        Find vehicle currently IN parking, dựa hoàn toàn trên bảng history.

        Xe đang trong bãi = bản ghi gần nhất có:
        - plate_id khớp
        - status = 'IN'
        - exit_time IS NULL
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM history
                WHERE plate_id = ?
                  AND status = 'IN'
                  AND exit_time IS NULL
                ORDER BY entry_time DESC, created_at DESC
                LIMIT 1
                """,
                (plate_id,),
            )

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
        """
        Get vehicles currently IN parking, dựa trên bảng history.

        Điều kiện:
        - status = 'IN'
        - exit_time IS NULL
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM history
                WHERE status = 'IN'
                  AND exit_time IS NULL
                ORDER BY entry_time DESC, created_at DESC
                """
            )

            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]

    def get_history(self, limit=100, offset=0, today_only=False, status=None, search=None, in_parking_only=False, entries_only=False):
        """Get vehicle history with optional search - Query từ HISTORY table"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query tu HISTORY table (khong phai vehicles)
            query = "SELECT * FROM history WHERE 1=1"
            params = []

            if today_only:
                query += " AND DATE(created_at) = DATE('now')"

            if in_parking_only:
                # Filter "Trong bai" - Chi lay xe DANG TRONG BAI (status='IN' va exit_time IS NULL)
                query += " AND status = 'IN' AND exit_time IS NULL"
            elif entries_only:
                # Filter "VAO" - Lay TAT CA cac lan vao (bao gom ca da ra)
                # Moi record trong history deu la mot lan vao, khong can filter them
                pass
            elif status:
                # Filter "RA" - Lay cac lan ra (status='OUT')
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
        """
        Get parking statistics.

        Toàn bộ thống kê (kể cả 'Trong bãi') đều lấy từ bảng history.
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Vehicles in parking: cac ban ghi status='IN' chua co exit_time
            cursor.execute(
                """
                SELECT COUNT(*) FROM history
                WHERE status = 'IN' AND exit_time IS NULL
                """
            )
            vehicles_in = cursor.fetchone()[0]

            # Total entries today (dem tu history - so lan vao hom nay)
            cursor.execute(
                """
                SELECT COUNT(*) FROM history 
                WHERE DATE(entry_time) = DATE('now')
                """
            )
            entries_today = cursor.fetchone()[0]

            # Total exits today (dem tu history - so lan ra hom nay)
            cursor.execute(
                """
                SELECT COUNT(*) FROM history 
                WHERE status = 'OUT' AND DATE(exit_time) = DATE('now')
                """
            )
            exits_today = cursor.fetchone()[0]

            # Total revenue today (tinh tu history - tong phi cac lan ra hom nay)
            cursor.execute(
                """
                SELECT SUM(fee) FROM history 
                WHERE status = 'OUT' AND DATE(exit_time) = DATE('now')
                """
            )
            revenue = cursor.fetchone()[0] or 0

            conn.close()

            return {
                "vehicles_in_parking": vehicles_in,
                "entries_today": entries_today,
                "exits_today": exits_today,
                "revenue_today": revenue,
            }

    def update_history_entry(self, history_id, new_plate_id, new_plate_view):
        """Update biển số trong history entry và lưu lịch sử thay đổi"""
        import json
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                # Lay record cu
                cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
                old_record = cursor.fetchone()
                if not old_record:
                    return False

                old_data = dict(old_record)

                # Update record
                cursor.execute("""
                    UPDATE history
                    SET plate_id = ?, plate_view = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_plate_id, new_plate_view, history_id))

                # Lay record moi
                cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
                new_record = cursor.fetchone()
                new_data = dict(new_record)

                # Luu lich su thay doi
                cursor.execute("""
                    INSERT INTO history_changes (
                        history_id, change_type, old_plate_id, old_plate_view,
                        new_plate_id, new_plate_view, old_data, new_data
                    ) VALUES (?, 'UPDATE', ?, ?, ?, ?, ?, ?)
                """, (
                    history_id,
                    old_data.get('plate_id'),
                    old_data.get('plate_view'),
                    new_plate_id,
                    new_plate_view,
                    json.dumps(old_data),
                    json.dumps(new_data)
                ))

                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                print(f"Error updating history entry: {e}")
                return False
            finally:
                conn.close()

    def delete_history_entry(self, history_id):
        """Delete history entry và lưu lịch sử thay đổi"""
        import json
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            try:
                # Lay record cu
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
                old_record = cursor.fetchone()
                if not old_record:
                    return False

                old_data = dict(old_record)

                # Luu lich su thay doi truoc khi xoa
                cursor.execute("""
                    INSERT INTO history_changes (
                        history_id, change_type, old_plate_id, old_plate_view,
                        old_data
                    ) VALUES (?, 'DELETE', ?, ?, ?)
                """, (
                    history_id,
                    old_data.get('plate_id'),
                    old_data.get('plate_view'),
                    json.dumps(old_data)
                ))

                # Xoa record trong history
                cursor.execute("DELETE FROM history WHERE id = ?", (history_id,))

                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                print(f"Error deleting history entry: {e}")
                return False
            finally:
                conn.close()

    def get_history_entry_by_id(self, history_id):
        """Lấy 1 bản ghi history theo id (kèm event_id)"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM history WHERE id = ? LIMIT 1", (history_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            except Exception as e:
                print(f"Error get_history_entry_by_id: {e}")
                return None
            finally:
                conn.close()

    def find_history_by_event_id(self, event_id):
        """Tìm bản ghi history theo event_id (dùng cho sync từ edge/p2p)"""
        if not event_id:
            return None
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM history WHERE event_id = ? LIMIT 1", (event_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            except Exception as e:
                print(f"Error find_history_by_event_id: {e}")
                return None
            finally:
                conn.close()

    def get_history_changes(self, limit=100, offset=0, history_id=None):
        """Get lịch sử thay đổi"""
        import json
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM history_changes WHERE 1=1"
            params = []

            if history_id:
                query += " AND history_id = ?"
                params.append(history_id)

            query += " ORDER BY changed_at DESC LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            changes = []
            for row in results:
                change = dict(row)
                # Parse JSON data
                if change.get('old_data'):
                    try:
                        change['old_data'] = json.loads(change['old_data'])
                    except:
                        pass
                if change.get('new_data'):
                    try:
                        change['new_data'] = json.loads(change['new_data'])
                    except:
                        pass
                changes.append(change)

            return changes

    def find_vehicle_in_parking(self, plate_id):
        """
        Find vehicle currently in parking lot (status = IN)
        Returns entry dict or None
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, plate_id, plate_view, entry_time, status,
                       last_location, last_location_time, is_anomaly
                FROM history
                WHERE plate_id = ? AND status = 'IN'
                ORDER BY entry_time DESC
                LIMIT 1
            """, (plate_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "id": row[0],
                    "plate_id": row[1],
                    "plate_view": row[2],
                    "entry_time": row[3],
                    "status": row[4],
                    "last_location": row[5],
                    "last_location_time": row[6],
                    "is_anomaly": row[7]
                }
            return None

    def update_vehicle_location(self, plate_id, location, location_time):
        """
        Update location for vehicle currently in parking lot
        Returns True if updated, False if vehicle not in parking
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE history
                SET last_location = ?,
                    last_location_time = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE plate_id = ? AND status = 'IN'
            """, (location, location_time, plate_id))

            rows_updated = cursor.rowcount
            conn.commit()
            conn.close()

            return rows_updated > 0

    def get_vehicles_at_location(self, location):
        """
        Get all vehicles currently at a specific parking lot location
        Returns list of vehicle dicts
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, plate_id, plate_view, entry_time,
                       last_location, last_location_time, is_anomaly
                FROM history
                WHERE last_location = ? AND status = 'IN'
                ORDER BY last_location_time DESC
            """, (location,))

            rows = cursor.fetchall()
            conn.close()

            vehicles = []
            for row in rows:
                vehicles.append({
                    "id": row["id"],
                    "plate_id": row["plate_id"],
                    "plate_view": row["plate_view"],
                    "entry_time": row["entry_time"],
                    "location": row["last_location"],
                    "location_time": row["last_location_time"],
                    "is_anomaly": row["is_anomaly"]
                })
            return vehicles

    def save_parking_lot_config(self, location_name, capacity, camera_id, camera_type="PARKING_LOT", edge_id=None):
        """
        Save or update parking lot configuration to database
        This allows parking lot config to persist even after camera type changes
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO parking_lots (location_name, capacity, camera_id, camera_type, edge_id, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(location_name) DO UPDATE SET
                    capacity = excluded.capacity,
                    camera_id = excluded.camera_id,
                    camera_type = excluded.camera_type,
                    edge_id = excluded.edge_id,
                    updated_at = CURRENT_TIMESTAMP
            """, (location_name, capacity, camera_id, camera_type, edge_id))

            conn.commit()
            conn.close()
            print(f"[CentralDB] Saved parking lot config: {location_name}, capacity={capacity}")

    def get_all_parking_lots(self):
        """
        Get all parking lot configurations from database
        Returns list of parking lot configs with their current occupancy
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, location_name, capacity, camera_id, camera_type, edge_id, created_at, updated_at
                FROM parking_lots
                ORDER BY location_name
            """)

            rows = cursor.fetchall()
            conn.close()

            parking_lots = []
            for row in rows:
                parking_lots.append({
                    "id": row["id"],
                    "location_name": row["location_name"],
                    "capacity": row["capacity"],
                    "camera_id": row["camera_id"],
                    "camera_type": row["camera_type"],
                    "edge_id": row["edge_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
            return parking_lots

    def create_entry_from_parking_lot(self, event_id, source_central, edge_id,
                                       plate_id, plate_view, entry_time,
                                       camera_name, location, location_time):
        """
        Auto-create entry when vehicle detected by PARKING_LOT camera but not in DB
        Mark as anomaly (is_anomaly = 1)
        """
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO history (
                    event_id, source_central, edge_id,
                    plate_id, plate_view,
                    entry_time, entry_camera_name, entry_confidence, entry_source,
                    last_location, last_location_time,
                    status, is_anomaly, sync_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                event_id, source_central, edge_id,
                plate_id, plate_view,
                entry_time, f"Auto-detected: {camera_name}", 0.0, "parking_lot_auto",
                location, location_time,
                "IN", 1, "P2P"  # is_anomaly = 1, sync_status = P2P
            ))

            entry_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return entry_id

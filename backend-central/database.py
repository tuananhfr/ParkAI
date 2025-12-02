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

            # Table: vehicles (trạng thái xe trong bãi - CHỈ LƯU XE ĐANG TRONG BÃI)
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

            # Table: history (lưu TOÀN BỘ lịch sử vào/ra - KHÔNG CÓ UNIQUE CONSTRAINT)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

            # Table: history_changes (lưu lịch sử thay đổi biển số)
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

            conn.commit()
            conn.close()

    def add_vehicle_entry(self, plate_id, plate_view, entry_time, camera_id, camera_name, confidence, source):
        """Add vehicle entry - Lưu vào cả vehicles (state) và history (log)"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            try:
                # 1. Lưu vào HISTORY table (LUÔN LUÔN INSERT - Không bao giờ ghi đè)
                cursor.execute("""
                    INSERT INTO history (
                        plate_id, plate_view, entry_time, entry_camera_id, entry_camera_name,
                        entry_confidence, entry_source, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'IN')
                """, (plate_id, plate_view, entry_time, camera_id, camera_name, confidence, source))

                history_id = cursor.lastrowid

                # 2. Lưu/Update vào VEHICLES table (state hiện tại)
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

                except sqlite3.IntegrityError:
                    # UNIQUE constraint - xe đã tồn tại trong vehicles
                    cursor.execute("""
                        SELECT id, status FROM vehicles WHERE plate_id = ?
                    """, (plate_id,))
                    existing = cursor.fetchone()

                    if existing and existing[1] == 'IN':
                        # Xe đang trong bãi - không cho vào lại
                        conn.rollback()
                        raise Exception(f"Xe {plate_view} đã VÀO lúc trước đó")
                    else:
                        # Xe đã ra - cho phép vào lại bằng cách UPDATE vehicles
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
        """Update vehicle exit - Cập nhật cả vehicles (state) và history (log)"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # 1. Update VEHICLES table (state)
            cursor.execute("""
                UPDATE vehicles
                SET exit_time = ?, exit_camera_id = ?, exit_camera_name = ?,
                    exit_confidence = ?, exit_source = ?, duration = ?, fee = ?,
                    status = 'OUT', updated_at = CURRENT_TIMESTAMP
                WHERE plate_id = ? AND status = 'IN'
            """, (exit_time, camera_id, camera_name, confidence, source, duration, fee, plate_id))

            rows_updated = cursor.rowcount

            # 2. Update HISTORY table (tìm record IN gần nhất và update)
            if rows_updated > 0:
                cursor.execute("""
                    UPDATE history
                    SET exit_time = ?, exit_camera_id = ?, exit_camera_name = ?,
                        exit_confidence = ?, exit_source = ?, duration = ?, fee = ?,
                        status = 'OUT', updated_at = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT id FROM history
                        WHERE plate_id = ? AND status = 'IN'
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                """, (exit_time, camera_id, camera_name, confidence, source, duration, fee, plate_id))

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

    def get_history(self, limit=100, offset=0, today_only=False, status=None, search=None, in_parking_only=False, entries_only=False):
        """Get vehicle history with optional search - Query từ HISTORY table"""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query từ HISTORY table (không phải vehicles)
            query = "SELECT * FROM history WHERE 1=1"
            params = []

            if today_only:
                query += " AND DATE(created_at) = DATE('now')"

            if in_parking_only:
                # Filter "Trong bãi" - Chỉ lấy xe ĐANG TRONG BÃI (status='IN' và exit_time IS NULL)
                query += " AND status = 'IN' AND exit_time IS NULL"
            elif entries_only:
                # Filter "VÀO" - Lấy TẤT CẢ các lần vào (bao gồm cả đã ra)
                # Mọi record trong history đều là một lần vào, không cần filter thêm
                pass
            elif status:
                # Filter "RA" - Lấy các lần ra (status='OUT')
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

            # Vehicles in parking (từ bảng vehicles - trạng thái hiện tại)
            cursor.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'IN'")
            vehicles_in = cursor.fetchone()[0]

            # Total entries today (đếm từ history - số lần vào hôm nay)
            cursor.execute("""
                SELECT COUNT(*) FROM history 
                WHERE DATE(entry_time) = DATE('now')
            """)
            entries_today = cursor.fetchone()[0]

            # Total exits today (đếm từ history - số lần ra hôm nay)
            cursor.execute("""
                SELECT COUNT(*) FROM history 
                WHERE status = 'OUT' AND DATE(exit_time) = DATE('now')
            """)
            exits_today = cursor.fetchone()[0]

            # Total revenue today (tính từ history - tổng phí các lần ra hôm nay)
            cursor.execute("""
                SELECT SUM(fee) FROM history 
                WHERE status = 'OUT' AND DATE(exit_time) = DATE('now')
            """)
            revenue = cursor.fetchone()[0] or 0

            conn.close()

            return {
                "vehicles_in_parking": vehicles_in,
                "entries_today": entries_today,
                "exits_today": exits_today,
                "revenue_today": revenue
            }

    def update_history_entry(self, history_id, new_plate_id, new_plate_view):
        """Update biển số trong history entry và lưu lịch sử thay đổi"""
        import json
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                # Lấy record cũ
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

                # Lấy record mới
                cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
                new_record = cursor.fetchone()
                new_data = dict(new_record)

                # Lưu lịch sử thay đổi
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
                print(f"❌ Error updating history entry: {e}")
                return False
            finally:
                conn.close()

    def delete_history_entry(self, history_id):
        """Delete history entry và lưu lịch sử thay đổi"""
        import json
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                # Lấy record cũ
                cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
                old_record = cursor.fetchone()
                if not old_record:
                    return False

                old_data = dict(old_record)

                # Lưu lịch sử thay đổi trước khi xóa
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

                # Xóa record
                cursor.execute("DELETE FROM history WHERE id = ?", (history_id,))

                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                print(f"❌ Error deleting history entry: {e}")
                return False
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

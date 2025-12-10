"""
SQLite Database Manager
Mỗi camera có DB local riêng, sync về server tổng cuối ngày
"""
import sqlite3
import os
from datetime import datetime
from threading import Lock

class Database:
    """SQLite Database Manager - Thread-safe"""

    def __init__(self, db_file="data/parking.db"):
        self.db_file = db_file
        self.lock = Lock()

        # Tao thu muc neu chua co
        os.makedirs(os.path.dirname(db_file), exist_ok=True)

        # Khoi tao database
        self._init_db()

    def _get_connection(self):
        """Tạo connection mới (để tránh lỗi thread)"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row  # De query tra ve dict
        return conn

    def _init_db(self):
        """Tạo bảng nếu chưa có"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Plate info
                    plate_id TEXT NOT NULL,           -- Raw: 30A12345
                    plate_view TEXT NOT NULL,         -- Display: 30A-123.45

                    -- Entry info (VÀO)
                    entry_time TEXT,                  -- YYYY-MM-DD HH:MM:SS
                    entry_camera_id INTEGER,
                    entry_camera_name TEXT,
                    entry_confidence REAL,
                    entry_source TEXT,                -- auto | manual

                    -- Exit info (RA)
                    exit_time TEXT,
                    exit_camera_id INTEGER,
                    exit_camera_name TEXT,
                    exit_confidence REAL,
                    exit_source TEXT,

                    -- Calculated
                    duration TEXT,                    -- "2 giờ 30 phút"
                    fee INTEGER DEFAULT 0,            -- Phí gửi xe (VNĐ)
                    status TEXT NOT NULL,             -- IN | OUT

                    -- Timestamps
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table: history_changes (luu lich su thay doi bien so) - giong central nhung tham chieu entries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    history_id INTEGER NOT NULL,       -- id trong bảng entries
                    change_type TEXT NOT NULL,         -- 'UPDATE' hoặc 'DELETE'
                    old_plate_id TEXT,
                    old_plate_view TEXT,
                    new_plate_id TEXT,
                    new_plate_view TEXT,
                    old_data TEXT,                     -- JSON của toàn bộ record cũ
                    new_data TEXT,                     -- JSON của toàn bộ record mới (nếu UPDATE)
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

            # Index cho performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_plate_id
                ON entries(plate_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON entries(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entry_time
                ON entries(entry_time)
            """)

            # Migration: Add event_id column for sync deduplication
            try:
                cursor.execute("ALTER TABLE entries ADD COLUMN event_id TEXT")
                print("[Database] Added event_id column to entries table")
            except sqlite3.OperationalError:
                # Column already exists
                pass

            # Index for event_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_id
                ON entries(event_id)
            """)

            conn.commit()
            conn.close()


    def add_entry(self, plate_id, plate_view, camera_id, camera_name,
                  confidence, source, status="IN"):
        """
        Thêm entry VÀO

        Return: entry_id
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO entries (
                    plate_id, plate_view,
                    entry_time, entry_camera_id, entry_camera_name,
                    entry_confidence, entry_source,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plate_id, plate_view,
                current_time, camera_id, camera_name,
                confidence, source,
                status
            ))

            entry_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return entry_id

    def update_exit(self, entry_id, camera_id, camera_name,
                    confidence, source, duration, fee):
        """
        Update thông tin RA
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE entries SET
                    exit_time = ?,
                    exit_camera_id = ?,
                    exit_camera_name = ?,
                    exit_confidence = ?,
                    exit_source = ?,
                    duration = ?,
                    fee = ?,
                    status = 'OUT',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                current_time, camera_id, camera_name,
                confidence, source,
                duration, fee,
                entry_id
            ))

            conn.commit()
            conn.close()

    def find_entry_in(self, plate_id):
        """
        Tìm entry IN gần nhất của xe

        Return: dict hoặc None
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM entries
                WHERE plate_id = ? AND status = 'IN'
                ORDER BY entry_time DESC
                LIMIT 1
            """, (plate_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

    def get_history(self, limit=100, offset=0, today_only=False, status=None, search=None):
        """
        Lấy lịch sử

        Args:
            limit: Số lượng records
            offset: Skip N records đầu
            today_only: Chỉ lấy hôm nay
            status: Filter theo status (IN | OUT)
            search: Search theo plate_id hoặc plate_view

        Return: list of dict
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM entries WHERE 1=1"
            params = []

            if today_only:
                today = datetime.now().strftime("%Y-%m-%d")
                query += " AND date(entry_time) = ?"
                params.append(today)

            if status:
                query += " AND status = ?"
                params.append(status)

            if search:
                query += " AND (plate_id LIKE ? OR plate_view LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

    def get_stats(self):
        """
        Thống kê

        Return: dict
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            today = datetime.now().strftime("%Y-%m-%d")

            # Total all time
            cursor.execute("SELECT COUNT(*) FROM entries")
            total_all = cursor.fetchone()[0]

            # Today stats
            cursor.execute("""
                SELECT COUNT(*) FROM entries
                WHERE date(entry_time) = ?
            """, (today,))
            today_total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM entries
                WHERE date(entry_time) = ? AND status = 'IN'
            """, (today,))
            today_in = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM entries
                WHERE date(entry_time) = ? AND status = 'OUT'
            """, (today,))
            today_out = cursor.fetchone()[0]

            # Total fee today
            cursor.execute("""
                SELECT SUM(fee) FROM entries
                WHERE date(entry_time) = ? AND status = 'OUT'
            """, (today,))
            today_fee = cursor.fetchone()[0] or 0

            # Vehicles inside
            cursor.execute("""
                SELECT COUNT(*) FROM entries WHERE status = 'IN'
            """)
            vehicles_inside = cursor.fetchone()[0]

            conn.close()

            return {
                "total_all_time": total_all,
                "today_total": today_total,
                "today_in": today_in,
                "today_out": today_out,
                "today_fee": today_fee,
                "vehicles_inside": vehicles_inside
            }

    def export_to_json(self):
        """
        Export toàn bộ DB ra JSON (để sync lên server)

        Return: list of dict
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM entries ORDER BY id")
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

    def clear_old_data(self, days=30):
        """
        Xóa data cũ hơn N ngày
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cutoff_date = datetime.now().strftime("%Y-%m-%d")

            cursor.execute("""
                DELETE FROM entries
                WHERE date(entry_time) < date(?, '-' || ? || ' days')
            """, (cutoff_date, days))

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            print(f" Deleted {deleted} old entries")
            return deleted

    def update_history_entry(self, history_id, new_plate_id, new_plate_view):
        """Update biển số trong history entry và lưu lịch sử thay đổi (giống central)"""
        import json
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                # Lay record cu
                cursor.execute("SELECT * FROM entries WHERE id = ?", (history_id,))
                old_record = cursor.fetchone()
                if not old_record:
                    return False

                old_data = dict(old_record)

                # Update record
                cursor.execute("""
                    UPDATE entries
                    SET plate_id = ?, plate_view = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_plate_id, new_plate_view, history_id))

                # Lay record moi
                cursor.execute("SELECT * FROM entries WHERE id = ?", (history_id,))
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
                print(f"Error updating history entry (edge): {e}")
                return False
            finally:
                conn.close()

    def delete_history_entry(self, history_id):
        """Delete history entry và lưu lịch sử thay đổi (giống central)"""
        import json
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                # Lay record cu
                cursor.execute("SELECT * FROM entries WHERE id = ?", (history_id,))
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

                # Xoa record trong entries
                cursor.execute("DELETE FROM entries WHERE id = ?", (history_id,))

                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                print(f"Error deleting history entry (edge): {e}")
                return False
            finally:
                conn.close()

    def get_history_changes(self, limit=100, offset=0, history_id=None):
        """Get lịch sử thay đổi (giống central)"""
        import json
        with self.lock:
            conn = self._get_connection()
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

    # ===== Methods for Central Sync =====

    def event_exists(self, event_id: str) -> bool:
        """Check if event_id already exists in database"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM entries WHERE event_id = ? LIMIT 1",
                (event_id,)
            )

            result = cursor.fetchone()
            conn.close()

            return result is not None

    def add_entry_with_event_id(self, event_id, plate_id, plate_view, entry_time, camera_id, camera_name,
                                  confidence, source, status="IN"):
        """Add entry with event_id for deduplication"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO entries (
                    event_id, plate_id, plate_view, entry_time,
                    entry_camera_id, entry_camera_name,
                    entry_confidence, entry_source, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, plate_id, plate_view, entry_time,
                camera_id, camera_name,
                confidence, source, status
            ))

            entry_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return entry_id

    def update_exit_by_event_id(self, event_id, exit_time, camera_id, camera_name,
                                  confidence, source, duration, fee):
        """Update exit info by event_id (for sync)"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE entries
                SET exit_time = ?, exit_camera_id = ?, exit_camera_name = ?,
                    exit_confidence = ?, exit_source = ?, duration = ?, fee = ?,
                    status = 'OUT', updated_at = CURRENT_TIMESTAMP
                WHERE event_id = ? AND status = 'IN'
            """, (
                exit_time, camera_id, camera_name,
                confidence, source, duration, fee,
                event_id
            ))

            rows_updated = cursor.rowcount
            conn.commit()
            conn.close()

            return rows_updated > 0

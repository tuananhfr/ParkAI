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

        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(db_file), exist_ok=True)

        # Khởi tạo database
        self._init_db()

    def _get_connection(self):
        """Tạo connection mới (để tránh lỗi thread)"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row  # Để query trả về dict
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

    def get_history(self, limit=100, today_only=False, status=None):
        """
        Lấy lịch sử

        Args:
            limit: Số lượng records
            today_only: Chỉ lấy hôm nay
            status: Filter theo status (IN | OUT)

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

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

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

            print(f"🗑️  Deleted {deleted} old entries")
            return deleted

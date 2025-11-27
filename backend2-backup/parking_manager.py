"""
Parking Manager - Sử dụng SQLite
"""
import re
from datetime import datetime
from database import Database

class ParkingManager:
    """Quản lý parking với SQLite"""

    def __init__(self, db_file="data/parking.db"):
        self.db = Database(db_file)

    def validate_plate(self, text):
        """
        Validate và format biển số VN

        Return: (plate_id, display_text)
        """
        if not text:
            return None, None

        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())

        patterns = [
            r"^[0-9]{2}[A-Z][0-9]{4,5}$",
            r"^[0-9]{3}[A-Z][0-9]{4,5}$",
        ]

        matched = False
        for pattern in patterns:
            if re.match(pattern, clean_text):
                matched = True
                break

        if not matched:
            return None, None

        # Format display
        if len(clean_text) == 8:
            prefix = clean_text[:3]
            suffix = clean_text[3:]
            display_text = f"{prefix}-{suffix[:3]}.{suffix[3:]}"
        elif len(clean_text) == 7:
            prefix = clean_text[:3]
            suffix = clean_text[3:]
            display_text = f"{prefix}-{suffix}"
        elif len(clean_text) == 9:
            prefix = clean_text[:4]
            suffix = clean_text[4:]
            display_text = f"{prefix}-{suffix[:3]}.{suffix[3:]}"
        else:
            display_text = clean_text

        return clean_text, display_text

    def process_entry(self, plate_text, camera_id, camera_type, camera_name,
                     confidence=0.0, source="manual"):
        """
        Xử lý entry từ camera

        Args:
            camera_type: "ENTRY" | "EXIT"
        """
        plate_id, display_text = self.validate_plate(plate_text)

        if not plate_id:
            return {
                "success": False,
                "error": "Biển số không hợp lệ"
            }

        if camera_type == "ENTRY":
            return self._process_entry(
                plate_id, display_text, camera_id, camera_name,
                confidence, source
            )
        elif camera_type == "EXIT":
            return self._process_exit(
                plate_id, display_text, camera_id, camera_name,
                confidence, source
            )
        else:
            return {
                "success": False,
                "error": f"Invalid camera type: {camera_type}"
            }

    def _process_entry(self, plate_id, display_text, camera_id, camera_name,
                      confidence, source):
        """Xử lý xe VÀO"""

        # Check duplicate
        existing = self.db.find_entry_in(plate_id)
        if existing:
            return {
                "success": False,
                "error": f"Xe {display_text} đã VÀO lúc {existing['entry_time']} tại {existing['entry_camera_name']}",
                "existing_entry": existing
            }

        # Thêm vào DB
        entry_id = self.db.add_entry(
            plate_id=plate_id,
            plate_view=display_text,
            camera_id=camera_id,
            camera_name=camera_name,
            confidence=confidence,
            source=source,
            status="IN"
        )

        print(f"✅ [{camera_name}] Xe {display_text} VÀO (ID: {entry_id})")

        return {
            "success": True,
            "action": "ENTRY",
            "entry_id": entry_id,
            "plate": display_text,
            "message": f"Xe {display_text} VÀO tại {camera_name}"
        }

    def _process_exit(self, plate_id, display_text, camera_id, camera_name,
                     confidence, source):
        """Xử lý xe RA"""

        # Tìm entry IN
        entry = self.db.find_entry_in(plate_id)

        if not entry:
            return {
                "success": False,
                "error": f"Xe {display_text} không có record VÀO!"
            }

        # Tính duration và fee
        duration = self.calculate_duration(entry['entry_time'], datetime.now())
        fee = self.calculate_fee(entry['entry_time'], datetime.now())

        # Update DB
        self.db.update_exit(
            entry_id=entry['id'],
            camera_id=camera_id,
            camera_name=camera_name,
            confidence=confidence,
            source=source,
            duration=duration,
            fee=fee
        )

        print(f"✅ [{camera_name}] Xe {display_text} RA. Phí: {fee:,}đ")

        return {
            "success": True,
            "action": "EXIT",
            "entry_id": entry['id'],
            "plate": display_text,
            "entry_time": entry['entry_time'],
            "duration": duration,
            "fee": fee,
            "message": f"Xe {display_text} RA. Phí: {fee:,}đ. Thời gian: {duration}"
        }

    def calculate_duration(self, entry_time, exit_time):
        """Tính thời gian gửi"""
        try:
            if isinstance(entry_time, str):
                entry_time = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
            if isinstance(exit_time, str):
                exit_time = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")

            delta = exit_time - entry_time
            total_seconds = int(delta.total_seconds())

            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60

            if days > 0:
                return f"{days} ngày {hours} giờ"
            elif hours > 0:
                return f"{hours} giờ {minutes} phút"
            else:
                return f"{minutes} phút"
        except:
            return ""

    def calculate_fee(self, entry_time, exit_time):
        """
        Tính phí gửi xe

        Logic:
        - 2 giờ đầu: 10,000đ
        - Mỗi giờ tiếp: 5,000đ
        - Qua đêm (>12h): 50,000đ
        - Qua ngày (>24h): 100,000đ/ngày
        """
        try:
            if isinstance(entry_time, str):
                entry_time = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
            if isinstance(exit_time, str):
                exit_time = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")

            delta = exit_time - entry_time
            hours = delta.total_seconds() / 3600

            if hours <= 2:
                return 10000
            elif hours <= 12:
                return 10000 + int((hours - 2) * 5000)
            elif hours <= 24:
                return 50000
            else:
                days = int(hours / 24)
                return days * 100000
        except:
            return 0

    def get_history(self, limit=100, today_only=False, status=None):
        """Lấy lịch sử"""
        return self.db.get_history(limit, today_only, status)

    def get_stats(self):
        """Thống kê"""
        return self.db.get_stats()

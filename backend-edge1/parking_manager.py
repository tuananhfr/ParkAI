"""
Parking Manager - Sử dụng SQLite
"""
import re
import json
import os
import httpx
from datetime import datetime
from database import Database

class ParkingManager:
    """Quản lý parking với SQLite"""

    def __init__(self, db_file="data/parking.db"):
        self.db = Database(db_file)
        self._subscription_cache = None
        self._subscription_cache_time = None

    def check_subscription(self, plate_id):
        """
        Kiểm tra xem biển số có trong danh sách thuê bao không

        Return: {
            "is_subscriber": True/False,
            "type": "company" | "monthly" | None,
            "owner_name": str | None
        }
        """
        try:
            # Cache subscriptions trong 60 giây để tránh đọc file liên tục
            now = datetime.now()
            if self._subscription_cache is None or \
               (self._subscription_cache_time and (now - self._subscription_cache_time).total_seconds() > 60):
                # Fetch subscriptions từ Central API
                import config
                central_url = config.CENTRAL_SERVER_URL

                try:
                    # Sync call (trong context này OK vì chỉ gọi 1 lần/60s)
                    import requests
                    response = requests.get(f"{central_url}/api/subscriptions", timeout=2)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            self._subscription_cache = data.get('subscriptions', [])
                            self._subscription_cache_time = now
                except Exception as e:
                    print(f"⚠️ Failed to fetch subscriptions from Central: {e}")
                    # Fallback: Try local file nếu Central down
                    try:
                        local_file = os.path.join(os.path.dirname(__file__), "../backend-central/data/subscriptions.json")
                        if os.path.exists(local_file):
                            with open(local_file, 'r', encoding='utf-8') as f:
                                self._subscription_cache = json.load(f)
                                self._subscription_cache_time = now
                    except Exception as e2:
                        print(f"⚠️ Failed to load local subscriptions: {e2}")
                        self._subscription_cache = []
                        self._subscription_cache_time = now

            # Search trong cache
            if not self._subscription_cache:
                return {
                    "is_subscriber": False,
                    "type": None,
                    "owner_name": None
                }

            # Normalize plate_id để so sánh (bỏ dấu gạch ngang, uppercase)
            normalized_plate = re.sub(r'[^A-Z0-9]', '', plate_id.upper())

            for sub in self._subscription_cache:
                # Normalize subscription plate
                sub_plate = re.sub(r'[^A-Z0-9]', '', sub.get('plate_number', '').upper())

                # Check match
                if sub_plate == normalized_plate:
                    # Check status và expiration
                    if sub.get('status') != 'active':
                        return {
                            "is_subscriber": False,
                            "type": None,
                            "owner_name": None,
                            "note": f"Thuê bao hết hạn hoặc inactive"
                        }

                    # Check expiration date (nếu có)
                    end_date = sub.get('end_date')
                    if end_date:
                        try:
                            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                            if now > end_dt:
                                return {
                                    "is_subscriber": False,
                                    "type": None,
                                    "owner_name": None,
                                    "note": f"Thuê bao hết hạn: {end_date}"
                                }
                        except:
                            pass

                    # Valid subscriber
                    return {
                        "is_subscriber": True,
                        "type": sub.get('type'),
                        "owner_name": sub.get('owner_name')
                    }

            # Not found
            return {
                "is_subscriber": False,
                "type": None,
                "owner_name": None
            }

        except Exception as e:
            print(f"❌ Error checking subscription: {e}")
            return {
                "is_subscriber": False,
                "type": None,
                "owner_name": None
            }

    def validate_plate(self, text):
        """
        Validate và format biển số VN

        Return: (plate_id, display_text)
        """
        if not text:
            return None, None

        # Bỏ ký tự đặc biệt, CHỈ GIỮ SỐ + CHỮ
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())

        # Patterns biển số VN: 2-3 số + 1-2 chữ + 4-6 số
        patterns = [
            r"^[0-9]{2}[A-Z]{1,2}[0-9]{4,6}$",   # 29A12345, 29AB12345, 29A1234, 29A112345
            r"^[0-9]{3}[A-Z]{1,2}[0-9]{4,6}$",   # 123A12345 (công vụ)
            r"^[0-9]{2}[A-Z][0-9][0-9]{4,5}$",   # 99E122268, 29A112345 (xe máy: 2 số + chữ + số + 4-5 số)
        ]

        matched = False
        for pattern in patterns:
            if re.match(pattern, clean_text):
                matched = True
                break

        if not matched:
            return None, None

        # Display text - GIỮ NGUYÊN text từ OCR (KHÔNG TỰ FORMAT)
        display_text = text.upper()

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
            clean_attempt = re.sub(r'[^A-Z0-9]', '', plate_text.upper()) if plate_text else None
            print(f"❌ Validate plate failed: '{plate_text}' (after clean: '{clean_attempt}')")
            return {
                "success": False,
                "error": f"Biển số không hợp lệ: {plate_text}"
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

        # Tính duration
        duration = self.calculate_duration(entry['entry_time'], datetime.now())

        # ===== CHECK SUBSCRIPTION - NẾU LÀ THUÊ BAO THÌ FEE = 0 =====
        subscription_info = self.check_subscription(plate_id)
        is_subscriber = subscription_info.get('is_subscriber', False)

        if is_subscriber:
            # Thuê bao → Miễn phí
            fee = 0
            customer_type = subscription_info.get('type', 'subscription')  # company, monthly
            print(f"✅ Xe {display_text} là THUÊ BAO ({customer_type}) - Miễn phí")
        else:
            # Khách lẻ → Tính phí bình thường
            fee = self.calculate_fee(entry['entry_time'], datetime.now())
            customer_type = "regular"
            print(f"💰 Xe {display_text} là KHÁCH LẺ - Phí: {fee:,}đ")

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


        return {
            "success": True,
            "action": "EXIT",
            "entry_id": entry['id'],
            "plate": display_text,
            "entry_time": entry['entry_time'],
            "duration": duration,
            "fee": fee,
            "customer_type": customer_type,  # Thêm loại khách
            "is_subscriber": is_subscriber,  # Thêm flag subscriber
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

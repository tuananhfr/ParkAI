"""
Parking Manager - Sử dụng SQLite
"""
import re
import json
import os
import httpx
import requests
from datetime import datetime
from database import Database

def _load_parking_fees():
    """
    Helper function để load parking fees từ API hoặc file JSON
    Returns: dict với keys: fee_base, fee_per_hour
    """
    import config
    
    parking_api_url = getattr(config, "PARKING_API_URL", "")
    parking_json_file = getattr(config, "PARKING_JSON_FILE", "data/parking_fees.json")
    
    try:
        if parking_api_url and parking_api_url.strip():
            # Goi API external
            response = requests.get(parking_api_url, timeout=5)
            if response.status_code == 200:
                fees_data = response.json()
                fees_dict = fees_data if isinstance(fees_data, dict) else fees_data.get("fees", {})
                
                # Luu vao file JSON de dung lam cache/fallback
                json_path = os.path.join(os.path.dirname(__file__), parking_json_file)
                os.makedirs(os.path.dirname(json_path), exist_ok=True)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(fees_dict, f, ensure_ascii=False, indent=2)
                
                return fees_dict
        else:
            # Doc tu file JSON
            json_path = os.path.join(os.path.dirname(__file__), parking_json_file)
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except Exception as e:
        print(f"Failed to load parking fees: {e}")
    
    # Fallback ve gia tri mac dinh tu config
    return {
        "fee_base": getattr(config, "FEE_BASE", 0.5),
        "fee_per_hour": getattr(config, "FEE_PER_HOUR", 25000)
    }


class ParkingManager:
    """Quản lý parking với SQLite"""

    def __init__(self, db_file="data/parking.db"):
        self.db = Database(db_file)
        self._subscription_cache = None
        self._subscription_cache_time = None
        self._fees_cache = None
        self._fees_cache_time = None

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
            # Cache subscriptions trong 60 giay de tranh doc file lien tuc
            now = datetime.now()
            if self._subscription_cache is None or \
               (self._subscription_cache_time and (now - self._subscription_cache_time).total_seconds() > 60):
                # Uu tien: Fetch subscriptions tu local edge API
                import config
                subscription_api_url = getattr(config, "SUBSCRIPTION_API_URL", "")
                subscription_json_file = getattr(config, "SUBSCRIPTION_JSON_FILE", "data/subscriptions.json")

                try:
                    if subscription_api_url and subscription_api_url.strip():
                        # Goi API external
                        import requests
                        response = requests.get(subscription_api_url, timeout=2)
                        if response.status_code == 200:
                            subscription_data = response.json()
                            self._subscription_cache = (
                                subscription_data
                                if isinstance(subscription_data, list)
                                else subscription_data.get("subscriptions", [])
                            )
                            self._subscription_cache_time = now
                        else:
                            raise Exception(f"API returned status {response.status_code}")
                    else:
                        # Doc tu file JSON local
                        json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
                        if os.path.exists(json_path):
                            with open(json_path, 'r', encoding='utf-8') as f:
                                self._subscription_cache = json.load(f)
                                self._subscription_cache_time = now
                        else:
                            # Fallback: Thu fetch tu Central neu co
                            central_url = getattr(config, "CENTRAL_SERVER_URL", "")
                            if central_url:
                                import requests
                                response = requests.get(f"{central_url}/api/subscriptions", timeout=2)
                                if response.status_code == 200:
                                    data = response.json()
                                    if data.get('success'):
                                        self._subscription_cache = data.get('subscriptions', [])
                                        self._subscription_cache_time = now
                                    else:
                                        self._subscription_cache = []
                                        self._subscription_cache_time = now
                                else:
                                    self._subscription_cache = []
                                    self._subscription_cache_time = now
                            else:
                                # Khong co central_url, set cache rong
                                self._subscription_cache = []
                                self._subscription_cache_time = now
                except Exception as e:
                    print(f"Failed to fetch subscriptions: {e}")
                    self._subscription_cache = []
                    self._subscription_cache_time = now

            # Search trong cache
            if not self._subscription_cache:
                return {
                    "is_subscriber": False,
                    "type": None,
                    "owner_name": None
                }

            # Normalize plate_id de so sanh (bo dau gach ngang, uppercase)
            normalized_plate = re.sub(r'[^A-Z0-9]', '', plate_id.upper())

            for sub in self._subscription_cache:
                # Normalize subscription plate
                sub_plate = re.sub(r'[^A-Z0-9]', '', sub.get('plate_number', '').upper())

                # Check match
                if sub_plate == normalized_plate:
                    # Check status va expiration
                    if sub.get('status') != 'active':
                        return {
                            "is_subscriber": False,
                            "type": None,
                            "owner_name": None,
                            "note": f"Thuê bao hết hạn hoặc inactive"
                        }

                    # Check expiration date (neu co)
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
            print(f"Error checking subscription: {e}")
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

        # Bo ky tu dac biet, CHI GIU SO + CHU
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())

        # Patterns bien so VN: 2-3 so + 1-2 chu + 4-6 so
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

        # Display text - GIU NGUYEN text tu OCR (KHONG TU FORMAT)
        display_text = text.upper()

        return clean_text, display_text

    def process_entry(self, plate_text, camera_id, camera_type, camera_name,
                     confidence=0.0, source="manual", event_id=None):
        """
        Xử lý entry từ camera

        Args:
            camera_type: "ENTRY" | "EXIT" | "PARKING_LOT"
            event_id: Event ID cho deduplication (optional, sẽ tạo tự động nếu None)
        """
        plate_id, display_text = self.validate_plate(plate_text)

        if not plate_id:
            clean_attempt = re.sub(r'[^A-Z0-9]', '', plate_text.upper()) if plate_text else None
            print(f"Validate plate failed: '{plate_text}' (after clean: '{clean_attempt}')")
            return {
                "success": False,
                "error": f"Biển số không hợp lệ: {plate_text}"
            }

        if camera_type == "ENTRY":
            return self._process_entry(
                plate_id, display_text, camera_id, camera_name,
                confidence, source, event_id
            )
        elif camera_type == "EXIT":
            return self._process_exit(
                plate_id, display_text, camera_id, camera_name,
                confidence, source, event_id
            )
        elif camera_type == "PARKING_LOT":
            return self._process_parking_lot(
                plate_id, display_text, camera_id, camera_name,
                confidence, source, event_id
            )
        else:
            return {
                "success": False,
                "error": f"Invalid camera type: {camera_type}"
            }

    def _process_entry(self, plate_id, display_text, camera_id, camera_name,
                      confidence, source, event_id=None):
        """Xử lý xe VÀO"""

        # Check duplicate by event_id first (nếu có)
        if event_id and self.db.event_exists(event_id):
            return {
                "success": False,
                "error": f"Event {event_id} đã tồn tại (duplicate)",
                "duplicate": True
            }

        # Check duplicate by plate
        existing = self.db.find_entry_in(plate_id)
        if existing:
            return {
                "success": False,
                "error": f"Xe {display_text} đã VÀO lúc {existing['entry_time']} tại {existing['entry_camera_name']}",
                "existing_entry": existing
            }

        entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Tạo event_id nếu chưa có
        if not event_id:
            ms = int(datetime.now().timestamp() * 1000)
            event_id = f"edge-{camera_id}_{ms}_{plate_id}"

        # Lưu vào DB với event_id
        entry_id = self.db.add_entry_with_event_id(
            event_id=event_id,
            plate_id=plate_id,
            plate_view=display_text,
            entry_time=entry_time,
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
            "event_id": event_id,  # Trả về event_id để sync
            "plate": display_text,
            "plate_id": plate_id,
            "entry_time": entry_time,
            "message": f"Xe {display_text} VÀO tại {camera_name}"
        }

    def _process_exit(self, plate_id, display_text, camera_id, camera_name,
                     confidence, source, event_id=None):
        """Xử lý xe RA"""

        # Tim entry IN
        entry = self.db.find_entry_in(plate_id)

        if not entry:
            return {
                "success": False,
                "error": f"Xe {display_text} không có record VÀO!"
            }

        # Lấy event_id của record IN nếu chưa có
        if not event_id:
            event_id = entry.get("event_id")

        # Tinh duration
        duration = self.calculate_duration(entry['entry_time'], datetime.now())

        # CHECK SUBSCRIPTION - NEU LA THUE BAO THI FEE = 0
        subscription_info = self.check_subscription(plate_id)
        is_subscriber = subscription_info.get('is_subscriber', False)

        if is_subscriber:
            # Thue bao → Mien phi
            fee = 0
            customer_type = subscription_info.get('type', 'subscription')  # company, monthly
            print(f"Xe {display_text} là THUÊ BAO ({customer_type}) - Miễn phí")
        else:
            # Khach le → Tinh phi binh thuong
            fee = self.calculate_fee(entry['entry_time'], datetime.now())
            customer_type = "regular"
            print(f"Xe {display_text} là KHÁCH LẺ - Phí: {fee:,}đ")

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
            "plate_id": plate_id,
            "entry_time": entry['entry_time'],
            "duration": duration,
            "fee": fee,
            "customer_type": customer_type,  # Thêm loại khách
            "is_subscriber": is_subscriber,  # Thêm flag subscriber
            "event_id": event_id,
            "message": f"Xe {display_text} RA. Phí: {fee:,}đ. Thời gian: {duration}"
        }

    def _process_parking_lot(self, plate_id, display_text, camera_id, camera_name,
                             confidence, source, event_id=None):
        """
        Xử lý detection từ camera PARKING_LOT (camera trong bãi)

        Logic:
        - Nếu xe ĐÃ trong bãi (status=IN): Cập nhật vị trí
        - Nếu xe CHƯA trong bãi: Tự động tạo entry (đánh dấu anomaly)
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check duplicate by event_id (nếu có)
        if event_id and self.db.event_exists(event_id):
            return {
                "success": False,
                "error": f"Event {event_id} đã tồn tại (duplicate)",
                "duplicate": True
            }

        # Kiểm tra xe có trong bãi không
        vehicle = self.db.find_vehicle_in_parking(plate_id)

        if vehicle:
            # ✅ Case 1: Xe ĐÃ trong bãi → Update location
            success = self.db.update_vehicle_location(
                plate_id=plate_id,
                location=camera_name,
                location_time=current_time
            )

            if success:
                print(f"[PARKING_LOT] Updated location for {display_text}: {camera_name}")
                return {
                    "success": True,
                    "action": "LOCATION_UPDATE",
                    "plate": display_text,
                    "plate_id": plate_id,
                    "location": camera_name,
                    "location_time": current_time,
                    "is_anomaly": False,
                    "event_id": event_id,
                    "message": f"Xe {display_text} đang ở {camera_name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to update location for {display_text}"
                }
        else:
            # ⚠️ Case 2: Xe CHƯA trong bãi → Tự động tạo entry (anomaly)
            # Generate event_id if not provided
            if not event_id:
                ms = int(datetime.now().timestamp() * 1000)
                event_id = f"edge-{camera_id}_{ms}_{plate_id}"

            entry_id = self.db.create_entry_from_parking_lot(
                event_id=event_id,
                plate_id=plate_id,
                plate_view=display_text,
                entry_time=current_time,
                camera_name=camera_name,
                location=camera_name,
                location_time=current_time
            )

            if entry_id:
                print(f"⚠️ [PARKING_LOT] Auto-created entry for {display_text} (ANOMALY)")
                return {
                    "success": True,
                    "action": "AUTO_ENTRY",
                    "entry_id": entry_id,
                    "plate": display_text,
                    "plate_id": plate_id,
                    "location": camera_name,
                    "location_time": current_time,
                    "is_anomaly": True,
                    "event_id": event_id,
                    "message": f"⚠️ Xe {display_text} được tự động tạo entry tại {camera_name} (ANOMALY)"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create entry for {display_text}"
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
        Load fees từ API/file JSON thay vì hardcode
        """
        try:
            if isinstance(entry_time, str):
                entry_time = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
            if isinstance(exit_time, str):
                exit_time = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")

            delta = exit_time - entry_time
            duration_hours = delta.total_seconds() / 3600

            # Load parking fees tu API/file JSON (cache 60 giay)
            now = datetime.now()
            if self._fees_cache is None or \
               (self._fees_cache_time and (now - self._fees_cache_time).total_seconds() > 60):
                self._fees_cache = _load_parking_fees()
                self._fees_cache_time = now
            
            fees = self._fees_cache
            free_hours = fees.get("fee_base", 0.5) or 0
            hourly_fee = fees.get("fee_per_hour", 25000) or 0

            if duration_hours <= free_hours:
                fee = 0
            else:
                billable_hours = duration_hours - free_hours
                # Lam tron len de tinh theo tung gio
                import math
                fee = math.ceil(billable_hours) * hourly_fee

            return fee
        except Exception as e:
            print(f"Error calculating fee: {e}")
            return 0

    def get_history(self, limit=100, today_only=False, status=None):
        """Lấy lịch sử"""
        return self.db.get_history(limit, today_only, status)

    def get_stats(self):
        """Thống kê"""
        return self.db.get_stats()

    # ===== Methods for Central Sync =====

    def event_exists(self, event_id: str) -> bool:
        """Check if event_id already exists in database"""
        return self.db.event_exists(event_id)

    def add_entry_from_sync(self, event_id: str, plate_id: str, plate_view: str, entry_time: str, source: str):
        """
        Add entry from central sync (from other nodes)
        Similar to add_entry but with event_id for deduplication
        """
        return self.db.add_entry_with_event_id(
            event_id=event_id,
            plate_id=plate_id,
            plate_view=plate_view,
            entry_time=entry_time,
            camera_id=None,  # Remote event, no local camera
            camera_name="Remote",
            confidence=0.0,
            source=source,
            status="IN"
        )

    def update_exit_from_sync(self, event_id: str, exit_time: str, fee: int, duration: str, source: str):
        """
        Update exit from central sync (from other nodes)
        Find entry by event_id and update exit info
        """
        return self.db.update_exit_by_event_id(
            event_id=event_id,
            exit_time=exit_time,
            camera_id=None,
            camera_name="Remote",
            confidence=0.0,
            source=source,
            duration=duration,
            fee=fee
        )

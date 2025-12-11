"""
Parking State Manager - Xử lý events từ Edge và cập nhật state
"""
from datetime import datetime
import re
import json
import os
import requests


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


class ParkingStateManager:
    """Quản lý trạng thái bãi xe từ events của Edge cameras"""

    def __init__(self, database, p2p_broadcaster=None):
        self.db = database
        self.p2p_broadcaster = p2p_broadcaster
        self._fees_cache = None
        self._fees_cache_time = None

    def process_edge_event(self, event_type, camera_id, camera_name, camera_type, data, event_id=None):
        """
        Process event từ Edge camera

        Args:
            event_type: "ENTRY" | "EXIT" | "DETECTION"
            camera_id: Camera ID
            camera_name: Camera name
            camera_type: "ENTRY" | "EXIT"
            data: Event data (plate_text, confidence, source, etc.)
        """
        plate_text = data.get('plate_text', '').strip().upper()
        confidence = data.get('confidence', 0.0)
        source = data.get('source', 'manual')

        # Normalize plate - Edge da validate roi, chi can normalize
        plate_id, plate_view = self._normalize_plate(plate_text)
        if not plate_id:
            return {
                "success": False,
                "error": f"Không thể normalize biển số: {plate_text}"
            }

        # Log event to database
        self.db.add_event(
            event_type=event_type,
            camera_id=camera_id,
            camera_name=camera_name,
            camera_type=camera_type,
            plate_text=plate_text,
            confidence=confidence,
            source=source,
            data=data
        )

        if event_type == "ENTRY" or event_type == "DETECTION":
            return self._process_entry(
                plate_id,
                plate_view,
                camera_id,
                camera_name,
                confidence,
                source,
                event_id=event_id,
                edge_id=data.get('edge_id'),
            )
        elif event_type == "EXIT":
            return self._process_exit(
                plate_id,
                plate_view,
                camera_id,
                camera_name,
                confidence,
                source,
                event_id=event_id
            )
        else:
            return {"success": False, "error": f"Unknown event type: {event_type}"}

    def _process_entry(self, plate_id, plate_view, camera_id, camera_name, confidence, source, event_id=None, edge_id=None):
        """Process vehicle entry"""
        # Chống lặp: nếu xe đang IN chưa ra thì không thêm bản ghi mới
        existing = self.db.find_vehicle_in_parking(plate_id)
        if existing:
            return {
                "success": False,
                "error": f"Xe {plate_view} đã ở trong bãi (vào lúc {existing.get('entry_time')})",
                "already_inside": True,
                "entry_time": existing.get("entry_time"),
                "event_id": existing.get("event_id"),
            }

        # Add entry
        entry_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            history_id = self.db.add_vehicle_entry(
                plate_id=plate_id,
                plate_view=plate_view,
                entry_time=entry_time,
                camera_id=camera_id,
                camera_name=camera_name,
                confidence=confidence,
                source=source,
                event_id=event_id,
                source_central=None,
                edge_id=edge_id,
                sync_status="LOCAL",
            )

            if history_id:
                return {
                    "success": True,
                    "action": "ENTRY",
                    "message": f"Xe {plate_view} VÀO bãi",
                    "plate_id": plate_id,
                    "plate_view": plate_view,
                    "history_id": history_id,
                    "entry_time": entry_time,
                    "event_id": event_id,
                }
            else:
                return {
                    "success": False,
                    "error": f"Không thể lưu xe {plate_view} vào database"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _process_exit(self, plate_id, plate_view, camera_id, camera_name, confidence, source, event_id=None):
        """Process vehicle exit"""
        # Find entry record
        entry = self.db.find_vehicle_in_parking(plate_id)
        if not entry:
            return {
                "success": False,
                "error": f"Xe {plate_view} không có record VÀO! Vui lòng kiểm tra."
            }

        # Lấy event_id từ record nếu chưa có (để sync P2P/Edges)
        if not event_id:
            event_id = entry.get("event_id")
            if not event_id:
                # Entry doesn't have event_id (old entry) - generate one
                import time
                ms = int(time.time() * 1000)
                event_id = f"central-{camera_id}_{ms}_{plate_id}"

        # Calculate duration and fee
        exit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        duration, fee = self._calculate_fee(entry['entry_time'], exit_time)

        # Update exit
        self.db.update_vehicle_exit(
            plate_id=plate_id,
            exit_time=exit_time,
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
            "message": f"Xe {plate_view} RA bãi",
            "plate_id": plate_id,
            "plate_view": plate_view,
            "history_id": entry.get("id"),
            "entry_time": entry['entry_time'],
            "exit_time": exit_time,
            "duration": duration,
            "fee": fee,
            "event_id": event_id,
        }

    def _normalize_plate(self, text):
        """
        Normalize biển số - Edge đã validate rồi, chỉ cần normalize
        
        Chỉ cần:
        - Clean text (bỏ ký tự đặc biệt)
        - Giữ nguyên display text từ edge
        """
        if not text:
            return None, None

        # Clean text - BO TAT CA KY TU DAC BIET (giu so + chu)
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        if len(clean_text) < 6:  # Toi thieu 6 ky tu
            return None, None

        # Display text - GIU NGUYEN text tu edge (khong tu format)
        plate_view = text.upper().strip()

        return clean_text, plate_view

    def _calculate_fee(self, entry_time_str, exit_time_str):
        """Calculate parking fee"""
        from datetime import datetime
        import math

        entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S')
        exit_time = datetime.strptime(exit_time_str, '%Y-%m-%d %H:%M:%S')

        duration_seconds = (exit_time - entry_time).total_seconds()
        duration_hours = duration_seconds / 3600

        # Format duration
        hours = int(duration_hours)
        minutes = int((duration_hours - hours) * 60)
        duration_str = f"{hours} giờ {minutes} phút"

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
            fee = math.ceil(billable_hours) * hourly_fee

        return duration_str, fee

    def get_parking_state(self):
        """Get current parking state"""
        vehicles = self.db.get_vehicles_in_parking()
        stats = self.db.get_stats()

        return {
            "vehicles_in_parking": vehicles,
            "stats": stats
        }

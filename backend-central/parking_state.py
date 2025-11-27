"""
Parking State Manager - Xử lý events từ Edge và cập nhật state
"""
from datetime import datetime
import re


class ParkingStateManager:
    """Quản lý trạng thái bãi xe từ events của Edge cameras"""

    def __init__(self, database):
        self.db = database

    def process_edge_event(self, event_type, camera_id, camera_name, camera_type, data):
        """
        Process event từ Edge camera

        Args:
            event_type: "ENTRY" | "EXIT"
            camera_id: Camera ID
            camera_name: Camera name
            camera_type: "ENTRY" | "EXIT"
            data: Event data (plate_text, confidence, source, etc.)
        """
        plate_text = data.get('plate_text', '').strip().upper()
        confidence = data.get('confidence', 0.0)
        source = data.get('source', 'manual')

        # Validate plate
        plate_id, plate_view = self._validate_plate(plate_text)
        if not plate_id:
            return {
                "success": False,
                "error": f"Biển số không hợp lệ: {plate_text}"
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

        if event_type == "ENTRY":
            return self._process_entry(plate_id, plate_view, camera_id, camera_name, confidence, source)
        elif event_type == "EXIT":
            return self._process_exit(plate_id, plate_view, camera_id, camera_name, confidence, source)
        else:
            return {"success": False, "error": f"Unknown event type: {event_type}"}

    def _process_entry(self, plate_id, plate_view, camera_id, camera_name, confidence, source):
        """Process vehicle entry"""
        # Check if vehicle already IN
        existing = self.db.find_vehicle_in_parking(plate_id)
        if existing:
            return {
                "success": False,
                "error": f"Xe {plate_view} đã VÀO lúc {existing['entry_time']} ({existing['entry_camera_name']})"
            }

        # Add entry
        entry_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        vehicle_id = self.db.add_vehicle_entry(
            plate_id=plate_id,
            plate_view=plate_view,
            entry_time=entry_time,
            camera_id=camera_id,
            camera_name=camera_name,
            confidence=confidence,
            source=source
        )

        return {
            "success": True,
            "action": "ENTRY",
            "message": f"Xe {plate_view} VÀO bãi",
            "plate_id": plate_id,
            "plate_view": plate_view,
            "vehicle_id": vehicle_id,
            "entry_time": entry_time
        }

    def _process_exit(self, plate_id, plate_view, camera_id, camera_name, confidence, source):
        """Process vehicle exit"""
        # Find entry record
        entry = self.db.find_vehicle_in_parking(plate_id)
        if not entry:
            return {
                "success": False,
                "error": f"Xe {plate_view} không có record VÀO! Vui lòng kiểm tra."
            }

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
            "entry_time": entry['entry_time'],
            "exit_time": exit_time,
            "duration": duration,
            "fee": fee
        }

    def _validate_plate(self, text):
        """Validate Vietnamese plate"""
        if not text or len(text) < 6:
            return None, None

        # Clean text
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())

        # Patterns
        patterns = [
            r'^\d{2}[A-HJ-NP-Z]\d{4,5}$',      # 29A12345
            r'^\d{3}[A-HJ-NP-Z]\d{4,5}$',      # 123A12345
        ]

        for pattern in patterns:
            if re.match(pattern, clean_text):
                # Format display: 30G-123.45
                if len(clean_text) == 8:  # 29A12345
                    plate_view = f"{clean_text[:3]}-{clean_text[3:6]}.{clean_text[6:]}"
                elif len(clean_text) == 9:  # 29A123456 hoặc 123A12345
                    if clean_text[2].isalpha():
                        plate_view = f"{clean_text[:3]}-{clean_text[3:6]}.{clean_text[6:]}"
                    else:
                        plate_view = f"{clean_text[:4]}-{clean_text[4:7]}.{clean_text[7:]}"
                else:
                    plate_view = clean_text

                return clean_text, plate_view

        return None, None

    def _calculate_fee(self, entry_time_str, exit_time_str):
        """Calculate parking fee"""
        from datetime import datetime
        import config

        entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S')
        exit_time = datetime.strptime(exit_time_str, '%Y-%m-%d %H:%M:%S')

        duration_seconds = (exit_time - entry_time).total_seconds()
        duration_hours = duration_seconds / 3600

        # Format duration
        hours = int(duration_hours)
        minutes = int((duration_hours - hours) * 60)
        duration_str = f"{hours} giờ {minutes} phút"

        # Calculate fee
        if duration_hours <= 2:
            fee = config.FEE_BASE
        else:
            fee = config.FEE_BASE + int((duration_hours - 2) * config.FEE_PER_HOUR)

        # Overnight charge
        if entry_time.hour >= 22 or exit_time.hour <= 6:
            fee += config.FEE_OVERNIGHT

        # Daily max
        if fee > config.FEE_DAILY_MAX:
            fee = config.FEE_DAILY_MAX

        return duration_str, fee

    def get_parking_state(self):
        """Get current parking state"""
        vehicles = self.db.get_vehicles_in_parking()
        stats = self.db.get_stats()

        return {
            "vehicles_in_parking": vehicles,
            "stats": stats
        }

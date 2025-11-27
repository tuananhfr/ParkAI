import json
import os
import re
import time
from datetime import datetime

class ParkingManager:
    def __init__(self, db_file="parking_history.json"):
        self.db_file = db_file
        self.history = self._load_db()
        self.cooldowns = {} 
        self.COOLDOWN_SECONDS = 15 # Xe phải khuất bóng 15s mới được tính lại

    def _load_db(self):
        """Load file lịch sử"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except:
                return []
        return []

    def _save_db(self):
        """Lưu file lịch sử"""
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=4)

    def validate_plate(self, text):
        if not text: return None, None
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())
        pattern = r"^[0-9]{2}[A-Z][0-9]{4,5}$"

        if re.match(pattern, clean_text):
            # BƯỚC 3: ĐỊNH DẠNG LẠI CHO ĐẸP (Formatter)
            # Để hiển thị lên web: 30A-123.45 hoặc 29C-1234
            
            prefix = clean_text[:3] # Lấy 3 ký tự đầu (30A)
            suffix = clean_text[3:] # Lấy phần số còn lại (12345)
            
            if len(suffix) == 5:
                # Nếu 5 số: Thêm dấu chấm sau 3 số đầu
                # 12345 -> 123.45
                display_text = f"{prefix}-{suffix[:3]}.{suffix[3:]}"
            else:
                # Nếu 4 số: Giữ nguyên
                display_text = f"{prefix}-{suffix}"
                
            return clean_text, display_text
        
        # Nếu không khớp Regex (ví dụ đọc nhầm biển báo, chữ trên áo...) -> Bỏ qua
        return None, None

    def calculate_duration(self, start_str, end_str):
        """Tính tổng thời gian gửi xe"""
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            t1 = datetime.strptime(start_str, fmt)
            t2 = datetime.strptime(end_str, fmt)
            delta = t2 - t1
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

    def get_history_list(self):
        """Lấy danh sách cho API (Mới nhất lên đầu)"""
        return sorted(self.history, key=lambda x: x['entry_time'], reverse=True)

    def process_plate(self, raw_text):
        """Logic xử lý sự kiện OCR"""
        
        # 1. Lọc biển số chuẩn VN
        plate_id, display_text = self.validate_plate(raw_text)
        
        # Nếu không phải biển chuẩn -> Trả về None ngay (Không làm gì cả)
        if not plate_id: 
            return None

        # 2. Check Cooldown (Tránh spam log khi xe dừng lâu trước cam)
        now = time.time()
        if plate_id in self.cooldowns:
            if now - self.cooldowns[plate_id] < self.COOLDOWN_SECONDS:
                return None
        self.cooldowns[plate_id] = now
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Tìm xem xe này đã VÀO chưa (tìm bản ghi 'IN' mới nhất)
        found_index = -1
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i]['plate_id'] == plate_id:
                if self.history[i]['status'] == 'IN':
                    found_index = i
                break

        result = None
        
        if found_index != -1:
            # === XE RA ===
            record = self.history[found_index]
            
            # Check logic: Phải cách ít nhất 60 giây mới được ra (tránh vừa vào đã tính ra)
            t_in = datetime.strptime(record['entry_time'], "%Y-%m-%d %H:%M:%S")
            t_out = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
            
            if (t_out - t_in).total_seconds() < 60:
                return None # Chưa đủ thời gian, bỏ qua

            # Cập nhật thông tin Ra
            record['exit_time'] = current_time
            record['duration'] = self.calculate_duration(record['entry_time'], current_time)
            record['status'] = 'OUT'
            
            result = {
                "text": display_text, 
                "status": "OUT",
                "message": f"Xe {display_text} ĐÃ RA. Tổng: {record['duration']}",
                "time": current_time
            }
        else:
            # === XE VÀO ===
            new_record = {
                "plate_id": plate_id,         # ID (30A12345)
                "plate_view": display_text,   # Hiển thị (30A-123.45)
                "entry_time": current_time,
                "exit_time": "",
                "duration": "",
                "status": "IN"
            }
            self.history.append(new_record)
            
            result = {
                "text": display_text,
                "status": "IN",
                "message": f"Xe {display_text} ĐÃ VÀO",
                "time": current_time
            }

        # Lưu file ngay lập tức
        if result:
            self._save_db()
            
        return result
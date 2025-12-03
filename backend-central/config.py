"""
Central Server Configuration
"""
import os

# ==================== SERVER ====================
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# ==================== DATABASE ====================
# SQLite database (tổng hợp từ tất cả cameras)
DB_FILE = "data/central.db"

# ==================== CAMERA REGISTRY ====================
# Timeout để đánh dấu camera offline (giây)
CAMERA_HEARTBEAT_TIMEOUT = 60  # 60s không nhận heartbeat → offline

# ==================== PARKING ====================
# Fee calculation - Nếu có PARKING_API_URL thì gọi API, nếu không thì dùng file JSON
PARKING_API_URL = os.getenv("PARKING_API_URL", "")  # Ví dụ: "https://api.example.com/parking/fees"
PARKING_JSON_FILE = "data/parking_fees.json"  # File JSON local mặc định

# Giá trị mặc định (fallback nếu không có API/file)
FEE_BASE = 0.5  # 0.5 giờ = 30 phút miễn phí
FEE_PER_HOUR = 25000  # 25k / giờ sau thời gian miễn phí
FEE_OVERNIGHT = 0  # Không dùng nữa (giữ để tương thích config_manager)
FEE_DAILY_MAX = 0  # Không giới hạn theo ngày

# ==================== STAFF MANAGEMENT ====================
# API endpoint để lấy danh sách người trực (để trống sẽ dùng file JSON local)
STAFF_API_URL = os.getenv("STAFF_API_URL", "")  # Ví dụ: "https://api.example.com/staff"
STAFF_JSON_FILE = "data/staff.json"  # File JSON local mặc định

# ==================== SUBSCRIPTION MANAGEMENT ====================
# API endpoint để lấy danh sách thuê bao (để trống sẽ dùng file JSON local)
SUBSCRIPTION_API_URL = os.getenv("SUBSCRIPTION_API_URL", "")  # Ví dụ: "https://api.example.com/subscriptions"
SUBSCRIPTION_JSON_FILE = "data/subscriptions.json"  # File JSON local mặc định

# ==================== REPORT MANAGEMENT ====================
# API endpoint để gửi báo cáo
REPORT_API_URL = os.getenv("REPORT_API_URL", "")  # Ví dụ: "https://api.example.com/reports"

# ==================== CENTRAL SERVER CONFIG ====================
# IP/URL của máy chủ central hiện tại
CENTRAL_SERVER_IP = os.getenv("CENTRAL_SERVER_IP", "")  # Ví dụ: "http://192.168.1.100:8000"
# Danh sách IP/URL các máy chủ central khác để đồng bộ dữ liệu (JSON string hoặc list)
CENTRAL_SYNC_SERVERS = os.getenv("CENTRAL_SYNC_SERVERS", "[]")  # Ví dụ: '["http://192.168.1.101:8000", "http://192.168.1.102:8000"]'

# ==================== EDGE CAMERA ROUTING ====================
# Mapping camera_id -> Edge backend URL để proxy WebRTC
# Điền URL thực tế thông qua biến môi trường (khuyến nghị) hoặc chỉnh trực tiếp.
EDGE_CAMERAS = {
    1: {
        "name": "Cổng A",
        "camera_type": "EXIT",
        "base_url": os.getenv("EDGE1_URL", "http://192.168.0.144:5000"),
        "ws_url": os.getenv(
            "EDGE1_WS_URL", "ws://192.168.0.144:5000/ws/detections"
        ),
        "default_mode": os.getenv("EDGE1_DEFAULT_MODE", "annotated"),
        "supports_annotated": True,
        "info_path": "/api/camera/info",
        "open_barrier_path": "/api/open-barrier",
    },
}

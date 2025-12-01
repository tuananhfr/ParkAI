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
# Fee calculation (giống Edge)
FEE_BASE = 10000  # 10k cho 2 giờ đầu
FEE_PER_HOUR = 5000  # 5k/giờ sau 2 giờ
FEE_OVERNIGHT = 50000  # 50k qua đêm (22h-6h)
FEE_DAILY_MAX = 100000  # 100k tối đa 1 ngày

# ==================== EDGE CAMERA ROUTING ====================
# Mapping camera_id -> Edge backend URL để proxy WebRTC
# Điền URL thực tế thông qua biến môi trường (khuyến nghị) hoặc chỉnh trực tiếp.
EDGE_CAMERAS = {
    1: {
        "name": "Cổng A",
        "base_url": os.getenv("EDGE1_URL", "http://192.168.0.144:5000"),
        "ws_url": os.getenv(
            "EDGE1_WS_URL", "ws://192.168.0.144:5000/ws/detections"
        ),
        "default_mode": os.getenv("EDGE1_DEFAULT_MODE", "annotated"),
        "supports_annotated": True,
        "info_path": "/api/camera/info",
        "open_barrier_path": "/api/open-barrier",
    },
    # Ví dụ thêm camera khác:
    # 2: {
    #     "name": "Cổng ra B",
    #     "base_url": os.getenv("EDGE2_URL", ""),
    #     "ws_url": os.getenv("EDGE2_WS_URL", ""),
    #     "default_mode": os.getenv("EDGE2_DEFAULT_MODE", "raw"),
    #     "supports_annotated": False,
    #     "info_path": "/api/camera/info",
    #     "open_barrier_path": "/api/open-barrier",
    # },
}

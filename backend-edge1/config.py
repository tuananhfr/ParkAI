"""
Edge Backend Configuration
"""
import os

# CONFIG - OPTIMAL FOR SMOOTH VIDEO 
# Plate detection model (IMX500)
MODEL_PATH = "/home/phamt/Desktop/parkAI/backend-edge1/models/network.rpk"
LABELS_PATH = "/home/phamt/Desktop/parkAI/backend-edge1/models/labels.txt"

# OCR model labels (nếu ONNX không có embedded names)
OCR_LABELS_PATH = "/home/phamt/Desktop/parkAI/backend/models/ocr_labels.txt"  # Path to OCR labels

# Camera settings - nâng lên 720p để stream rõ nét hơn
RESOLUTION_WIDTH = 1280
RESOLUTION_HEIGHT = 720
CAMERA_FPS = 30  # Giữ 30fps, Pi 5 + IMX500 vẫn đáp ứng tốt ở 720p

# Detection settings - Tối ưu cho DEV MODE (200 ảnh calibration)
DETECTION_FPS = 18  # tăng nhẹ để phù hợp với fps cao hơn, vẫn tránh quá tải OCR
DETECTION_THRESHOLD = 0.50  # Thấp hơn cho dev mode - model INT8 với 200 ảnh
IOU_THRESHOLD = 0.65
MAX_DETECTIONS = 10

# Aspect ratio filter - Accept cả biển 1 dòng & 2 dòng
# - Biển 1 dòng: aspect ~3.0-4.5 (rất ngang)
# - Biển 2 dòng: aspect ~1.2-2.0 (hơi ngang)
MIN_PLATE_ASPECT_RATIO = 1.0  # Accept boxes có width >= height (không dọc)

# Visual settings
BOX_COLOR = (0, 255, 0)
TEXT_COLOR = (255, 255, 255)
TEXT_BG_COLOR = (0, 255, 0)
BOX_THICKNESS = 2
TEXT_FONT_SCALE = 0.5
TEXT_FONT_THICKNESS = 1

COLOR_MODE = 'single'

# Performance settings - TẬN DỤNG IMX500, GIẢM CPU
MAX_FRAME_QUEUE_SIZE = 1  # Drop frames aggressively - chỉ giữ latest
MAX_DETECTION_QUEUE_SIZE = 1  # Chỉ metadata, không cần buffer nhiều

# OCR settings - Tối ưu độ chính xác với Voting
ENABLE_OCR = True
OCR_CONFIDENCE_THRESHOLD = 0.25  # YOLO OCR confidence
OCR_FRAME_SKIP = 1  # Chạy OCR mỗi frame (giảm từ 2 để có nhiều votes hơn, đọc nhanh hơn)

# TRIGGER-BASED APPROACH (Production for Pi) 
# Capture ảnh tĩnh khi confidence cao, OCR 1-2 lần, tiết kiệm CPU

# Capture settings
CAPTURE_CONFIDENCE_THRESHOLD = 0.60  # Confidence để capture ảnh (dev mode: 0.6)
MAX_OCR_ATTEMPTS = 2                 # OCR tối đa 2 lần trên ảnh đã capture
CAPTURE_TIMEOUT = 3.0                # Reset sau 3s nếu không có kết quả
CAPTURE_COOLDOWN = 2.0               # Chờ 2s sau khi xử lý xong mới capture tiếp

# Plate image settings - Gửi ảnh đã capture về frontend
PLATE_IMAGE_MIN_CONFIDENCE = 0.55  # Gửi ảnh khi capture (thấp hơn CAPTURE_THRESHOLD 1 chút)

# VOTING CONFIG - DEV MODE (200 ảnh calibration) 
# Real-time OCR + Voting để bù đắp confidence thấp

# Quick Open: Tắt cho dev mode - confidence hiếm khi đạt 0.9
QUICK_OPEN_ENABLED = False     # TẮT - model 200 ảnh hiếm khi đạt 0.9
QUICK_OPEN_CONFIDENCE = 0.90
QUICK_OPEN_MIN_LENGTH = 8

# Voting: Dùng nhiều để bù đắp confidence thấp
PLATE_VOTE_WINDOW = 1.2       # Tăng lên 1.2s để có nhiều votes hơn (dev mode)
PLATE_MIN_VOTES = 2           # Cần 2 votes giống nhau
PLATE_SIMILARITY_THRESHOLD = 0.85  # 85% giống nhau mới group
EARLY_STOP_ENABLED = True     # BẬT - Stop ngay khi đủ 2 votes

# ONNX OCR model (YOLO tự load class names)
ONNX_OCR_MODEL_PATH = "/home/phamt/Desktop/parkAI/backend-edge1/models/ocr.onnx"

# Server settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

# CAMERA IDENTIFICATION (MULTI-CAMERA SUPPORT) 
CAMERA_ID = 1  # Unique ID cho mỗi camera (1, 2, 3, ...)
CAMERA_NAME = "Cổng A"  # Tên hiển thị
CAMERA_TYPE = "ENTRY"  # "ENTRY" (vào) | "EXIT" (ra)
CAMERA_LOCATION = "Gate A"  # Vị trí
GATE = 1  # Gate number (1-10)

# DATABASE 
# SQLite database file (local trên mỗi camera)
DB_FILE = "data/parking.db"

# Nếu muốn mỗi camera có DB riêng (sync về server sau):
# DB_FILE = f"data/parking_cam{CAMERA_ID}.db"

# BARRIER CONTROL 
BARRIER_ENABLED = False  # Set True nếu có barrier
BARRIER_GPIO_PIN = 18  # GPIO pin điều khiển relay
BARRIER_AUTO_CLOSE_TIME = 5.0  # Tự động đóng sau 5 giây

# CENTRAL SERVER (để sync data) 
# Để trống nếu muốn sử dụng Edge standalone, hoặc nhập URL Central Server
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"  # Ví dụ: "http://192.168.0.144:8000" hoặc để trống cho standalone
CENTRAL_WS_URL = ""  # WebSocket URL (tự động tạo từ CENTRAL_SERVER_URL nếu có)
CENTRAL_SYNC_ENABLED = True  # Bật sync lên central server (tự động bật nếu có CENTRAL_SERVER_URL)

# OFFLINE MODE & FALLBACK 
# Offline exit strategy khi Central down + xe không có trong cache
# Choices: "ALLOW_FREE", "ALLOW_DEFAULT_FEE", "BLOCK", "QUERY_BACKUP"
OFFLINE_EXIT_STRATEGY = "ALLOW_DEFAULT_FEE"

# Default fee khi không tìm thấy entry record (offline mode)
DEFAULT_EXIT_FEE = 50000  # 50,000 VND

# Backup Central URLs để query khi Central chính down (QUERY_BACKUP strategy)
BACKUP_CENTRAL_URLS = [
    # "http://192.168.0.141:8001",  # Central Gate 1
    # "http://192.168.0.142:8002",  # Central Gate 2
]

# Offline queue database
OFFLINE_QUEUE_DB = "data/offline_queue.db"

# Vehicle cache database
VEHICLE_CACHE_DB = "data/edge_cache.db"

# PARKING FEE MANAGEMENT 
# Fee calculation - Nếu có PARKING_API_URL thì gọi API, nếu không thì dùng file JSON
PARKING_API_URL = os.getenv("PARKING_API_URL", "")  # Ví dụ: "https://api.example.com/parking/fees"
PARKING_JSON_FILE = "data/parking_fees.json"  # File JSON local mặc định

# Giá trị mặc định (fallback nếu không có API/file)
FEE_BASE = 0.5  # 0.5 giờ = 30 phút miễn phí
FEE_PER_HOUR = 25000  # 25k / giờ sau thời gian miễn phí
FEE_OVERNIGHT = 0  # Không dùng nữa (giữ để tương thích config_manager)
FEE_DAILY_MAX = 0  # Không giới hạn theo ngày

# STAFF MANAGEMENT 
# API endpoint để lấy danh sách người trực (để trống sẽ dùng file JSON local)
STAFF_API_URL = os.getenv("STAFF_API_URL", "")  # Ví dụ: "https://api.example.com/staff"
STAFF_JSON_FILE = "data/staff.json"  # File JSON local mặc định

# SUBSCRIPTION MANAGEMENT 
# API endpoint để lấy danh sách thuê bao (để trống sẽ dùng file JSON local)
SUBSCRIPTION_API_URL = os.getenv("SUBSCRIPTION_API_URL", "")  # Ví dụ: "https://api.example.com/subscriptions"
SUBSCRIPTION_JSON_FILE = "data/subscriptions.json"  # File JSON local mặc định

#

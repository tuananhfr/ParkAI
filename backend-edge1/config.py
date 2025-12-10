"""
Edge Backend Configuration
"""
import os

# CONFIG - OPTIMAL FOR SMOOTH VIDEO
# Plate detection model (IMX500)
MODEL_PATH = "/home/phamt/Desktop/parkAI/backend-edge1/models/network.rpk"
LABELS_PATH = "/home/phamt/Desktop/parkAI/backend-edge1/models/labels.txt"

# Camera settings - nang len 720p de stream ro net hon
RESOLUTION_WIDTH = 1280
RESOLUTION_HEIGHT = 720
CAMERA_FPS = 30  # Giu 30fps, Pi 5 + IMX500 van dap ung tot o 720p

# Detection settings - Toi uu cho DEV MODE (200 anh calibration)
DETECTION_FPS = 18  # tang nhe de phu hop voi fps cao hon, van tranh qua tai OCR
DETECTION_THRESHOLD = 0.50  # Thap hon cho dev mode - model INT8 voi 200 anh
IOU_THRESHOLD = 0.65
MAX_DETECTIONS = 10

# Aspect ratio filter - Accept ca bien 1 dong & 2 dong
# - Bien 1 dong: aspect ~3.0-4.5 (rat ngang)
# - Bien 2 dong: aspect ~1.2-2.0 (hoi ngang)
MIN_PLATE_ASPECT_RATIO = 1.0  # Accept boxes co width >= height (khong doc)

# Performance settings - TAN DUNG IMX500, GIAM CPU
MAX_FRAME_QUEUE_SIZE = 1  # Drop frames aggressively - chi giu latest
MAX_DETECTION_QUEUE_SIZE = 1  # Chi metadata, khong can buffer nhieu

# OCR settings - Toi uu do chinh xac voi Voting
ENABLE_OCR = True
OCR_CONFIDENCE_THRESHOLD = 0.25  # YOLO OCR confidence
OCR_FRAME_SKIP = 1  # Chay OCR moi frame (giam tu 2 de co nhieu votes hon, doc nhanh hon)

# TRIGGER-BASED APPROACH (Production for Pi)
# Capture anh tinh khi confidence cao, OCR 1-2 lan, tiet kiem CPU

# Capture settings
CAPTURE_CONFIDENCE_THRESHOLD = 0.60  # Confidence de capture anh (dev mode: 0.6)
MAX_OCR_ATTEMPTS = 2                 # OCR toi da 2 lan tren anh da capture
CAPTURE_TIMEOUT = 3.0                # Reset sau 3s neu khong co ket qua
CAPTURE_COOLDOWN = 2.0               # Cho 2s sau khi xu ly xong moi capture tiep

# Plate image settings - Gui anh da capture ve frontend
PLATE_IMAGE_MIN_CONFIDENCE = 0.55  # Gui anh khi capture (thap hon CAPTURE_THRESHOLD 1 chut)

# VOTING CONFIG - DEV MODE (200 anh calibration)
# Real-time OCR + Voting de bu dap confidence thap

# Quick Open: Tat cho dev mode - confidence hiem khi dat 0.9
QUICK_OPEN_ENABLED = False     # TAT - model 200 anh hiem khi dat 0.9

# Voting: Dung nhieu de bu dap confidence thap
PLATE_VOTE_WINDOW = 1.2       # Tang len 1.2s de co nhieu votes hon (dev mode)
PLATE_MIN_VOTES = 2           # Can 2 votes giong nhau
PLATE_SIMILARITY_THRESHOLD = 0.85  # 85% giong nhau moi group
EARLY_STOP_ENABLED = True     # BAT - Stop ngay khi du 2 votes

# ONNX OCR model (YOLO tu load class names)
ONNX_OCR_MODEL_PATH = "/home/phamt/Desktop/parkAI/backend-edge1/models/ocr.onnx"

# Server settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

# CAMERA IDENTIFICATION (MULTI-CAMERA SUPPORT)
CAMERA_ID = 1  # Unique ID cho moi camera (1, 2, 3, ...)
CAMERA_NAME = "Cổng A"  # Tên hiển thị
CAMERA_TYPE = "ENTRY"  # "ENTRY" (vào) | "EXIT" (ra)
CAMERA_LOCATION = "Gate A"  # Vị trí
GATE = 1  # Gate number (1-10)

# DATABASE
# SQLite database file (local tren moi camera)
DB_FILE = "data/parking.db"

# Neu muon moi camera co DB rieng (sync ve server sau):
# DB_FILE = f"data/parking_cam{CAMERA_ID}.db"

# BARRIER CONTROL - KHONG SU DUNG (Da xoa logic barrier)
# BARRIER_ENABLED = False
# BARRIER_GPIO_PIN = 18
# BARRIER_AUTO_CLOSE_TIME = 5.0

# CENTRAL SERVER (de sync data)
# De trong neu muon su dung Edge standalone, hoac nhap URL Central Server
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"  # Ví dụ: "http://192.168.0.144:8000" hoặc để trống cho standalone
CENTRAL_SYNC_ENABLED = True  # Bat sync len central server (tu dong bat neu co CENTRAL_SERVER_URL)

# PARKING FEE MANAGEMENT
# Fee calculation - Neu co PARKING_API_URL thi goi API, neu khong thi dung file JSON
PARKING_API_URL = os.getenv("PARKING_API_URL", "")  # Ví dụ: "https://api.example.com/parking/fees"
PARKING_JSON_FILE = "data/parking_fees.json"  # File JSON local mặc định

# Gia tri mac dinh (fallback neu khong co API/file)
FEE_BASE = 0.5  # 0.5 gio = 30 phut mien phi
FEE_PER_HOUR = 25000  # 25k / gio sau thoi gian mien phi

# STAFF MANAGEMENT
# API endpoint de lay danh sach nguoi truc (de trong se dung file JSON local)
STAFF_API_URL = os.getenv("STAFF_API_URL", "")  # Ví dụ: "https://api.example.com/staff"
STAFF_JSON_FILE = "data/staff.json"  # File JSON local mặc định

# SUBSCRIPTION MANAGEMENT
# API endpoint de lay danh sach thue bao (de trong se dung file JSON local)
SUBSCRIPTION_API_URL = os.getenv("SUBSCRIPTION_API_URL", "")  # Ví dụ: "https://api.example.com/subscriptions"
SUBSCRIPTION_JSON_FILE = "data/subscriptions.json"  # File JSON local mặc định



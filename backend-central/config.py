"""
Central Server Configuration
"""
import os

# SERVER
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# DATABASE
# SQLite database (tong hop tu tat ca cameras)
DB_FILE = "data/central.db"

# CAMERA REGISTRY
# Timeout de danh dau camera offline (giay)
CAMERA_HEARTBEAT_TIMEOUT = 60  # 60s khong nhan heartbeat → offline

# PARKING
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

# REPORT MANAGEMENT
# API endpoint de gui bao cao
REPORT_API_URL = os.getenv("REPORT_API_URL", "")  # Ví dụ: "https://api.example.com/reports"

# CENTRAL SERVER CONFIG
# IP/URL cua may chu central hien tai
CENTRAL_SERVER_IP = os.getenv("CENTRAL_SERVER_IP", "")  # Ví dụ: "http://192.168.1.100:8000"
# Danh sach IP/URL cac may chu central khac de dong bo du lieu (JSON string hoac list)
CENTRAL_SYNC_SERVERS = os.getenv("CENTRAL_SYNC_SERVERS", "[]")  # Ví dụ: '["http://192.168.1.101:8000", "http://192.168.1.102:8000"]'

# EDGE CAMERA ROUTING
# Mapping camera_id -> Edge backend URL de proxy WebRTC
# Dien URL thuc te thong qua bien moi truong (khuyen nghi) hoac chinh truc tiep.
EDGE_CAMERAS = {
}

# Multi-Camera Parking System - Setup Guide

## Architecture

```
Shared Backend Code (1 codebase)
├── database.py
├── parking_manager.py
├── barrier_controller.py
├── detection_service.py
├── app.py
└── config.py  ⭐ CHỈ FILE NÀY KHÁC NHAU MỖI CAMERA
```

## Setup Multi-Camera

### Camera 1 - Cổng vào A

```python
# backend2/config.py

CAMERA_ID = 1
CAMERA_NAME = "Cổng vào A"
CAMERA_TYPE = "ENTRY"  # VÀO
CAMERA_LOCATION = "Gate A"

DB_FILE = "data/parking.db"  # Shared DB nếu dùng NFS
# hoặc
# DB_FILE = f"data/parking_cam{CAMERA_ID}.db"  # DB riêng

BARRIER_ENABLED = True
BARRIER_GPIO_PIN = 18
```

### Camera 2 - Cổng ra A

```python
# backend2/config.py

CAMERA_ID = 2
CAMERA_NAME = "Cổng ra A"
CAMERA_TYPE = "EXIT"  # RA
CAMERA_LOCATION = "Gate A"

DB_FILE = "data/parking.db"  # Cùng DB với camera 1

BARRIER_ENABLED = True
BARRIER_GPIO_PIN = 18
```

### Camera 3 - Cổng vào B

```python
# backend2/config.py

CAMERA_ID = 3
CAMERA_NAME = "Cổng vào B"
CAMERA_TYPE = "ENTRY"
CAMERA_LOCATION = "Gate B"
```

## Database Options

### Option 1: Shared Database (NFS/Samba)

```bash
# Mount shared folder trên tất cả camera
sudo mount -t nfs 192.168.0.144:/parking-data /mnt/shared

# config.py (TẤT CẢ CAMERA)
DB_FILE = "/mnt/shared/parking.db"
```

**Ưu điểm:**

- ✅ Realtime sync
- ✅ 1 DB duy nhất
- ✅ Camera VÀO và RA share data

**Nhược điểm:**

- ❌ Phụ thuộc network

### Option 2: Local DB + Sync

```python
# config.py
DB_FILE = f"data/parking_cam{CAMERA_ID}.db"
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"
```

**Sync script (chạy cuối ngày):**

```python
# sync_to_server.py
import requests
import config
from parking_manager import ParkingManager

def sync_data():
    pm = ParkingManager(db_file=config.DB_FILE)
    data = pm.db.export_to_json()

    response = requests.post(
        f"{config.CENTRAL_SERVER_URL}/api/sync",
        json={
            "camera_id": config.CAMERA_ID,
            "data": data
        }
    )

    if response.ok:
        print("✅ Synced to central server")
        # Clear local data
        pm.db.clear_old_data(days=1)
```

## API Endpoints

### Open Barrier (Mở cửa)

```bash
POST /api/open-barrier
{
  "plate_text": "30G56789",
  "confidence": 0.92,
  "source": "auto"  # or "manual"
}

Response:
{
  "success": true,
  "action": "ENTRY",  # hoặc "EXIT"
  "entry_id": 123,
  "plate": "30G-123.45",
  "message": "Xe 30G-123.45 VÀO tại Cổng vào A",
  "barrier_opened": true,
  "camera_info": {
    "id": 1,
    "name": "Cổng vào A",
    "type": "ENTRY"
  }
}
```

### Get History

```bash
GET /api/history?limit=100&today_only=true&status=IN

Response:
{
  "success": true,
  "count": 45,
  "stats": {
    "total_all_time": 1234,
    "today_total": 45,
    "today_in": 23,
    "today_out": 22,
    "today_fee": 450000,
    "vehicles_inside": 1
  },
  "history": [...]
}
```

### Get Stats

```bash
GET /api/stats

Response:
{
  "success": true,
  "total_all_time": 1234,
  "today_total": 45,
  "today_in": 23,
  "today_out": 22,
  "today_fee": 450000,
  "vehicles_inside": 1
}
```

### Camera Info

```bash
GET /api/camera/info

Response:
{
  "success": true,
  "camera": {
    "id": 1,
    "name": "Cổng vào A",
    "type": "ENTRY",
    "location": "Gate A"
  }
}
```

## Database Schema

```sql
CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Plate info
    plate_id TEXT NOT NULL,           -- 30A12345
    plate_view TEXT NOT NULL,         -- 30A-123.45

    -- Entry info
    entry_time TEXT,
    entry_camera_id INTEGER,
    entry_camera_name TEXT,
    entry_confidence REAL,
    entry_source TEXT,                -- auto | manual

    -- Exit info
    exit_time TEXT,
    exit_camera_id INTEGER,
    exit_camera_name TEXT,
    exit_confidence REAL,
    exit_source TEXT,

    -- Calculated
    duration TEXT,                    -- "2 giờ 30 phút"
    fee INTEGER DEFAULT 0,
    status TEXT NOT NULL,             -- IN | OUT

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## Fee Calculation Logic

Default logic (có thể customize trong `parking_manager.py`):

- **2 giờ đầu**: 10,000đ
- **Mỗi giờ tiếp**: 5,000đ/giờ
- **Qua đêm (>12h)**: 50,000đ
- **Qua ngày (>24h)**: 100,000đ/ngày

## Deployment Checklist

### Mỗi camera cần:

1. ✅ Copy toàn bộ code backend2
2. ✅ Sửa `config.py`:
   - CAMERA_ID (unique)
   - CAMERA_NAME
   - CAMERA_TYPE (ENTRY/EXIT)
   - DB_FILE
3. ✅ Setup GPIO nếu có barrier
4. ✅ Chạy backend: `python app.py`
5. ✅ Test API endpoints

### Network setup:

- Camera VÀO và RA phải share DB (NFS hoặc sync)
- Hoặc setup central server để aggregate data

## Testing

```bash
# Test camera info
curl http://localhost:5000/api/camera/info

# Test entry
curl -X POST http://localhost:5000/api/open-barrier \
  -H "Content-Type: application/json" \
  -d '{"plate_text": "30G12345", "source": "manual"}'

# Test history
curl http://localhost:5000/api/history?today_only=true

# Test stats
curl http://localhost:5000/api/stats
```

## Troubleshooting

### Xe đã VÀO nhưng chưa RA

```python
# Kiểm tra DB
pm = ParkingManager()
entries = pm.get_history(status='IN')
print(entries)

# Force update xe RA (manual fix)
pm.db.update_exit(
    entry_id=123,
    camera_id=2,
    camera_name="Manual",
    confidence=1.0,
    source="manual",
    duration="2 giờ",
    fee=20000
)
```

### Database locked

Nếu dùng shared DB qua NFS, có thể gặp lock:

```python
# Tăng timeout
conn = sqlite3.connect(db_file, timeout=30.0)
```

Hoặc chuyển sang local DB + sync.

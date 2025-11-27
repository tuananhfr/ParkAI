# Kiến Trúc Production - Hệ Thống Quản Lý Bãi Xe

## 📋 Tổng Quan

Hệ thống gồm **3 thành phần chính**:

1. **Edge Backend** - Chạy trên mỗi Raspberry Pi (N cameras)
2. **Central Backend** - Server tổng (1 máy duy nhất)
3. **Frontend Dashboard** - Giao diện tổng cho bảo vệ

---

## 🏗️ Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                     EDGE LAYER (Raspberry Pi)               │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Camera 1     │  │ Camera 2     │  │ Camera N     │     │
│  │ (ENTRY)      │  │ (EXIT)       │  │ (ENTRY)      │     │
│  │              │  │              │  │              │     │
│  │ • IMX500 AI  │  │ • IMX500 AI  │  │ • IMX500 AI  │     │
│  │ • OCR        │  │ • OCR        │  │ • OCR        │     │
│  │ • SQLite     │  │ • SQLite     │  │ • SQLite     │     │
│  │ • Sync       │  │ • Sync       │  │ • Sync       │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │             │
│         └─────────────────┼─────────────────┘             │
│                           │                               │
└───────────────────────────┼───────────────────────────────┘
                            │
                            │ HTTP Events + Heartbeat
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   CENTRAL LAYER (Server)                    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │           Central Backend Server                   │    │
│  │                                                    │    │
│  │  • Nhận events từ Edge                            │    │
│  │  • Hợp nhất trạng thái bãi xe                     │    │
│  │  • Track camera online/offline                    │    │
│  │  • SQLite tổng hợp                                │    │
│  │  • API cho Frontend                               │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                               │
└───────────────────────────┼───────────────────────────────┘
                            │
                            │ HTTP API
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND LAYER (Dashboard)                 │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Dashboard Tổng (Bảo vệ)                   │    │
│  │                                                    │    │
│  │  • Grid N cameras (status online/offline)         │    │
│  │  • Xe trong bãi (realtime)                        │    │
│  │  • Stats (VÀO, RA, Doanh thu)                     │    │
│  │  • Lịch sử xe vào/ra                              │    │
│  │  • Chỉ gọi Central Backend                        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục

```
parkAI/
├── backend-edge/              # Edge Backend (deploy lên mỗi Pi)
│   ├── app.py                # FastAPI server
│   ├── config.py             # Config (CAMERA_ID, CENTRAL_URL)
│   ├── detection_service.py  # AI detection + OCR
│   ├── ocr_service.py        # OCR engine
│   ├── camera_manager.py     # IMX500 camera
│   ├── database.py           # SQLite local
│   ├── parking_manager.py    # Business logic
│   ├── barrier_controller.py # Barrier control
│   ├── central_sync.py       # Sync to Central
│   ├── websocket_manager.py  # WebSocket
│   └── requirements.txt
│
├── backend-central/           # Central Backend (1 server duy nhất)
│   ├── app.py                # FastAPI server
│   ├── config.py
│   ├── database.py           # SQLite tổng hợp
│   ├── parking_state.py      # Hợp nhất state từ Edge
│   ├── camera_registry.py    # Track cameras
│   └── requirements.txt
│
└── frontend-dashboard/        # Frontend Dashboard
    ├── src/
    │   ├── App.jsx           # Main dashboard
    │   ├── main.jsx
    │   └── index.css
    ├── index.html
    ├── vite.config.js
    └── package.json
```

---

## 🔄 Luồng Hoạt Động

### 1. Edge → Central (Event Sync)

```
┌─────────────┐
│ Edge Camera │
└──────┬──────┘
       │
       │ 1. Detect xe (IMX500 + OCR)
       │
       │ 2. Lưu SQLite local
       │
       │ 3. Gửi event lên Central
       │    POST /api/edge/event
       │    {
       │      type: "ENTRY" | "EXIT",
       │      camera_id: 1,
       │      camera_name: "Cổng vào A",
       │      data: {
       │        plate_text: "30G56789",
       │        confidence: 0.92
       │      }
       │    }
       ▼
┌─────────────┐
│   Central   │
│   Server    │
└─────────────┘
```

### 2. Edge → Central (Heartbeat)

```
Mỗi 30 giây, Edge gửi:

POST /api/edge/heartbeat
{
  camera_id: 1,
  camera_name: "Cổng vào A",
  status: "online",
  events_sent: 123,
  events_failed: 5
}
```

### 3. Frontend → Central (Query)

```
Frontend Dashboard gọi:

GET /api/cameras          # Danh sách cameras
GET /api/parking/state    # Xe trong bãi
GET /api/parking/history  # Lịch sử
GET /api/stats           # Thống kê
```

---

## 🚀 Triển Khai

### A. Cài Đặt Edge Backend (trên mỗi Raspberry Pi)

```bash
# 1. Copy code lên Pi
cd ~/parkAI
cp -r backend2/ backend-edge/

# 2. Config camera
cd backend-edge
nano config.py

# Sửa:
CAMERA_ID = 1                    # Unique ID (1, 2, 3, ...)
CAMERA_NAME = "Cổng vào A"       # Tên
CAMERA_TYPE = "ENTRY"            # ENTRY hoặc EXIT
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"  # IP Central server
CENTRAL_SYNC_ENABLED = True

# 3. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Chạy
python3 app.py
```

**Lặp lại cho Camera 2, 3, ... N** (chỉ đổi `CAMERA_ID`, `CAMERA_NAME`, `CAMERA_TYPE`)

---

### B. Cài Đặt Central Backend (1 server duy nhất)

```bash
# 1. Tạo thư mục
cd ~/parkAI
mkdir backend-central
cd backend-central

# Copy files (đã tạo sẵn)

# 2. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Chạy
python3 app.py
```

Server chạy tại: `http://192.168.0.144:8000`

---

### C. Cài Đặt Frontend Dashboard

```bash
# 1. Install Node.js dependencies
cd frontend-dashboard
npm install

# 2. Config Central URL
nano src/App.jsx
# Sửa: const CENTRAL_URL = "http://192.168.0.144:8000";

# 3. Chạy development
npm run dev

# 4. Build production
npm run build
# Files trong dist/ deploy lên web server
```

Dashboard chạy tại: `http://localhost:3001`

---

## 📡 API Endpoints

### Edge Backend (Port 5000)

| Endpoint            | Method    | Mô tả                          |
| ------------------- | --------- | ------------------------------ |
| `/api/status`       | GET       | Status của Edge camera         |
| `/api/open-barrier` | POST      | Mở cửa (gọi từ frontend local) |
| `/api/camera/info`  | GET       | Thông tin camera               |
| `/ws/detections`    | WebSocket | Stream detections realtime     |

### Central Backend (Port 8000)

| Endpoint               | Method | Mô tả                  |
| ---------------------- | ------ | ---------------------- |
| `/api/edge/event`      | POST   | Nhận event từ Edge     |
| `/api/edge/heartbeat`  | POST   | Nhận heartbeat từ Edge |
| `/api/cameras`         | GET    | Danh sách cameras      |
| `/api/parking/state`   | GET    | Xe trong bãi           |
| `/api/parking/history` | GET    | Lịch sử xe vào/ra      |
| `/api/stats`           | GET    | Thống kê               |

---

## ⚙️ Configuration

### Edge Backend (backend-edge/config.py)

```python
# Camera identification
CAMERA_ID = 1
CAMERA_NAME = "Cổng vào A"
CAMERA_TYPE = "ENTRY"  # ENTRY | EXIT

# Central server
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"
CENTRAL_SYNC_ENABLED = True

# Local database
DB_FILE = f"data/parking_cam{CAMERA_ID}.db"

# Barrier
BARRIER_ENABLED = True
BARRIER_GPIO_PIN = 18
```

### Central Backend (backend-central/config.py)

```python
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

DB_FILE = "data/central.db"

CAMERA_HEARTBEAT_TIMEOUT = 60  # Seconds
```

---

## 🔍 Monitoring

### Camera Status

Frontend Dashboard hiển thị:

- **Online**: Camera gửi heartbeat trong 60s gần nhất
- **Offline**: Không nhận heartbeat > 60s

### Logs

Edge Backend:

```
✅ OCR: 30G56789 (confidence: 0.92)
🌐 Central sync: Event sent successfully
⚠️  Central sync failed: Connection refused
```

Central Backend:

```
✅ Event processed: ENTRY from Camera 1 - Xe 30G-567.89 VÀO bãi
⚠️  Camera 2 (Cổng ra B) marked as OFFLINE
```

---

## 🛠️ Troubleshooting

### Edge không kết nối được Central

```bash
# Check network
ping 192.168.0.144

# Check Central server running
curl http://192.168.0.144:8000/api/status
```

### Camera offline trên Dashboard

- Check Edge backend còn chạy không: `ps aux | grep python`
- Check logs Edge: `journalctl -u parking-edge -f`
- Restart Edge: `systemctl restart parking-edge`

### Database conflict

Nếu Edge và Central dùng chung file:

```bash
# Edge: Dùng DB local riêng
DB_FILE = f"data/parking_cam{CAMERA_ID}.db"

# Central: Dùng DB riêng
DB_FILE = "data/central.db"
```

---

## ✅ Testing

### 1. Test Edge → Central Sync

```bash
# Terminal 1: Chạy Central
cd backend-central
python3 app.py

# Terminal 2: Chạy Edge Camera 1
cd backend-edge
CAMERA_ID=1 python3 app.py

# Terminal 3: Test event
curl -X POST http://localhost:5000/api/open-barrier \
  -H "Content-Type: application/json" \
  -d '{"plate_text":"30G56789","confidence":0.92,"source":"manual"}'

# Check Central log: ✅ Event processed
```

### 2. Test Dashboard

```bash
# Mở browser
http://localhost:3001

# Kiểm tra:
- Camera 1 hiển thị "online"
- Stats cập nhật
- Xe trong bãi hiển thị
```

---

## 📊 Performance

### Edge Backend

- Detection: 15 FPS
- OCR: Mỗi 10 frames (~0.7s/lần)
- Sync latency: < 100ms

### Central Backend

- Event processing: < 50ms
- API response: < 100ms
- Camera check: Mỗi 10s

### Frontend Dashboard

- Auto-refresh: Mỗi 5s
- UI update: < 50ms

---

## 🔐 Security (TODO)

- [ ] HTTPS cho Central API
- [ ] Authentication token cho Edge → Central
- [ ] Rate limiting
- [ ] Input validation
- [ ] SQL injection prevention

---

## 📝 Changelog

### v1.0.0 (2025-01-27)

- ✅ Edge Backend với sync to Central
- ✅ Central Backend với registry
- ✅ Frontend Dashboard tổng
- ✅ Multi-camera support
- ✅ Realtime stats + history

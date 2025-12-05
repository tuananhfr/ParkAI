# ParkAI System Architecture

## Tổng quan
ParkAI là hệ thống quản lý bãi xe thông minh với kiến trúc **Central-Edge** phân tán.

## Kiến trúc

```
Frontend (React/PyQt6) ←→ Central Backend ←→ Edge Backend (Raspberry Pi)
                             ↕ P2P Network
                          Other Centrals
```

## Backend Architecture

### Central Backend (Port 8000)
- **Framework**: FastAPI + Uvicorn
- **Database**: SQLite (`backend-central/data/central.db`)
- **Chức năng**: Tổng hợp dữ liệu, API cho frontend, P2P sync

**API Endpoints:**
```
# Frontend API
GET  /api/status              # Backend status
GET  /api/cameras             # Danh sách cameras
GET  /api/parking/history     # Lịch sử vào/ra
PUT  /api/parking/history/{id}# Cập nhật biển số
DELETE /api/parking/history/{id}

# WebRTC Proxy
POST /api/cameras/{id}/offer           # WebRTC raw video
POST /api/cameras/{id}/offer-annotated # WebRTC annotated video

# WebSocket
WS /ws/cameras                # Camera status real-time
WS /ws/history                # History updates real-time

# Edge Event API
POST /api/edge/event          # Nhận ENTRY/EXIT từ edge
POST /api/edge/heartbeat      # Nhận heartbeat từ edge
```

**WebSocket Message Format:**
```json
{
  "type": "cameras_update",
  "data": {
    "cameras": [
      {
        "id": 1,
        "name": "Cổng A",
        "type": "ENTRY",
        "status": "online",
        "stream_proxy": { "available": true },
        "control_proxy": { "available": true, "base_url": "..." }
      }
    ]
  }
}
```

### Edge Backend (Port 5000)
- **Framework**: FastAPI + aiortc
- **Hardware**: Raspberry Pi 5 + IMX500 AI module
- **Database**: SQLite (`backend-edge1/data/parking.db`)
- **Chức năng**: Camera detection, OCR, barrier control, sync với Central

**API Endpoints:**
```
# WebRTC Streaming
POST /offer               # Raw video
POST /offer-annotated     # Video with bounding boxes

# Detection
WS /ws/detections        # Real-time detections

# Barrier Control
POST /api/open-barrier   # Mở barrier
POST /api/close-barrier  # Đóng barrier
GET  /api/barrier/status # Status

# Info
GET  /api/status         # Edge status
GET  /api/camera/info    # Camera info
```

## Video Streaming Protocol: WebRTC

**Why WebRTC:**
- Real-time (< 1s latency)
- Browser-native support
- Adaptive bitrate
- NAT traversal

**Implementation:**
- Edge: `aiortc` library (Python)
- Frontend: Browser WebRTC API
- Bitrate: 2.5 Mbps
- Modes: Raw (RGB) và Annotated (với bounding boxes)

**WebRTC Flow:**
```
Frontend → Central → Edge
1. Frontend tạo offer (SDP)
2. POST /api/cameras/{id}/offer-annotated
3. Central proxy → Edge /offer-annotated
4. Edge tạo answer (SDP)
5. Answer returned → Frontend
6. Video stream established
```

## Database Schema

### Central Database
```sql
-- Lịch sử vào/ra
history (
  id, plate_id, plate_view,
  entry_time, entry_camera_id, entry_camera_name,
  exit_time, exit_camera_id, exit_camera_name,
  duration, fee, status
)

-- Registry cameras
cameras (
  id, name, type, status,
  last_heartbeat, events_sent, events_failed
)

-- Log events
events (
  id, event_type, camera_id, plate_text,
  confidence, source, timestamp
)
```

### Edge Database
```sql
-- Lịch sử local (giống central)
entries (
  id, plate_id, plate_view,
  entry_time, exit_time,
  duration, fee, status
)
```

## Entry/Exit Flow

### Entry Event
```
Edge:
1. Detect plate + OCR → "29A12345"
2. POST /api/edge/event (ENTRY) → Central
   {
     "type": "ENTRY",
     "camera_id": 1,
     "data": {
       "plate_text": "29A12345",
       "confidence": 0.92,
       "source": "auto"
     }
   }

Central:
3. Validate + normalize plate
4. Insert vào history (status=IN)
5. Broadcast WebSocket /ws/history

Frontend:
6. Update stats + history table
```

### Exit Event
```
Edge:
1. Detect exit plate
2. POST /api/edge/event (EXIT) → Central

Central:
3. Find existing ENTRY record
4. Update:
   - exit_time = now
   - fee = calculated
   - status = OUT
5. Broadcast WebSocket

Frontend:
6. Show fee + remove from "in parking"
```

## Plate Detection (OCR Voting)

**Strategy:**
```
1. Run detection @ 18 FPS (IMX500)
2. Confidence > 0.60? → Capture frame
3. Run OCR với voting:
   - Collect votes trong 1.2s window
   - Require min 2 votes giống nhau
   - 85% similarity threshold
4. Đủ votes? → Send event to Central
```

## P2P Network (Multi-Central)

**Config**: `backend-central/config/p2p_config.json`
```json
{
  "this_central": {
    "id": "central-1",
    "ip": "192.168.0.144",
    "p2p_port": 9000,
    "api_port": 8000
  },
  "peer_centrals": [
    {
      "id": "central-2",
      "ip": "192.168.0.145",
      "p2p_port": 9000
    }
  ]
}
```

**P2P Messages:**
- `VEHICLE_ENTRY_PENDING`: Xe vào từ central khác
- `VEHICLE_ENTRY_CONFIRMED`: Xác nhận entry
- `VEHICLE_EXIT`: Xe ra
- `HEARTBEAT`: Keep-alive
- `SYNC_REQUEST/RESPONSE`: Data sync

**Use Case:**
```
Location A (Central-1) → Xe vào
  ↓ P2P message
Location B (Central-2) → Nhận thông tin
  ↓ Khi xe ra ở B
Location B → Tính phí dựa trên entry từ A
```

## Important Notes

### Backend không có `/api/history` endpoint
Central backend có:
- ✅ `/api/parking/history` (GET/PUT/DELETE)
- ❌ `/api/history` (không tồn tại → 404 error)

### Camera stream_url = None
Backend không trả về `stream_url` trong `/api/cameras`.
Thay vào đó:
- `stream_proxy.available = true`
- Frontend dùng WebRTC offer để connect
- Không phải MJPEG/RTSP streaming

### WebSocket ping messages
Backend gửi "ping" text (không phải JSON).
Frontend phải ignore ping messages.

## Configuration

### Central Config (`backend-central/config.py`)
```python
EDGE_CAMERAS = {
    1: {
        "name": "Cổng A",
        "camera_type": "EXIT",
        "base_url": "http://192.168.0.144:5000",
        "ws_url": "ws://192.168.0.144:5000/ws/detections",
        "default_mode": "annotated",
    }
}
```

### Edge Config (`backend-edge1/config.py`)
```python
CAMERA_ID = 1
CAMERA_NAME = "Cổng A"
CAMERA_TYPE = "ENTRY"  # or "EXIT"
DETECTION_THRESHOLD = 0.50
CAPTURE_CONFIDENCE_THRESHOLD = 0.60
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"
```

## Frontend Implementations

### Frontend Web (React)
- **Tech**: React 18 + Vite + Bootstrap
- **WebRTC**: Browser WebRTC API
- **WebSocket**: 2 connections (`/ws/cameras`, `/ws/history`)
- **Components**: CameraView, VideoStream, HistoryPanel

### Frontend Desktop (PyQt6) - IN PROGRESS
- **Tech**: PyQt6 + Python
- **Video**: WebRTC với aiortc (planning)
- **Tabs**: Dashboard, Cameras, History, Settings
- **Status**: Phase 4 completed, Phase 5 implemented

## Desktop Frontend TODO
1. ✅ Fix WebSocket ping error
2. ⏳ Implement WebRTC video streaming (aiortc)
3. ⏳ Fix History API endpoint (use `/api/parking/history`)
4. ⏳ Test camera card with real stream

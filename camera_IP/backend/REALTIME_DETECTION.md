# Real-time License Plate Detection với WebSocket

Hướng dẫn sử dụng real-time detection với WebSocket + Canvas overlay (tương tự parkAI backend-edge1).

---

## Kiến trúc

```
Camera (RTSP/Webcam)
  ↓
Backend Detection Loop (detection_stream.py)
  ↓ detect license plates
WebSocket Broadcast (websocket_manager.py)
  ↓ send JSON detections
Frontend Canvas (test_websocket.html)
  ↓ draw bounding boxes
User sees real-time boxes
```

---

## Quick Start

### 1. Chạy Backend

```bash
cd backend
make.bat
# hoặc
python main.py
```

Backend sẽ khởi động với:
- **API**: http://localhost:5000
- **WebSocket**: ws://localhost:5000/ws/detections
- **Swagger Docs**: http://localhost:5000/docs

### 2. Mở Test Page

```bash
# Mở file trong browser
test_websocket.html
```

Hoặc truy cập: http://localhost:5000/docs và test API từ Swagger UI.

### 3. Start Detection

**Trong test_websocket.html:**

1. Nhập Camera ID: `camera1`
2. Nhập RTSP URL hoặc Camera Index:
   - `0` = Webcam mặc định
   - `1`, `2` = Camera khác
   - `rtsp://admin:password@192.168.1.100:554/stream` = RTSP stream
3. Điều chỉnh threshold nếu cần
4. Click **"▶️ Start Detection"**

**Bằng API:**

```bash
# Start detection cho webcam
curl -X POST "http://localhost:5000/api/detection/start/camera1?rtsp_url=0&conf_threshold=0.25"

# Start detection cho RTSP stream
curl -X POST "http://localhost:5000/api/detection/start/camera1?rtsp_url=rtsp://admin:pass@192.168.1.100:554/stream"
```

---

## API Endpoints

### 1. WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:5000/ws/detections');

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'detections') {
        const detections = message.data;
        // detections = [
        //   {
        //     "class": "license_plate",
        //     "confidence": 0.95,
        //     "bbox": [x, y, width, height],
        //     "camera_id": "camera1",
        //     "frame_id": 123,
        //     "timestamp": 1234567890.123
        //   }
        // ]
    }
};
```

### 2. Start Detection

```http
POST /api/detection/start/{camera_id}?rtsp_url=<url>&conf_threshold=0.25&iou_threshold=0.45
```

**Parameters:**
- `camera_id`: Unique identifier (e.g., "camera1", "front_door")
- `rtsp_url`: RTSP URL hoặc camera index (0, 1, 2...)
- `conf_threshold`: Confidence threshold (0.0-1.0, default: 0.25)
- `iou_threshold`: IOU threshold for NMS (0.0-1.0, default: 0.45)

**Response:**
```json
{
  "success": true,
  "message": "Detection started for camera camera1"
}
```

### 3. Stop Detection

```http
POST /api/detection/stop/{camera_id}
```

**Response:**
```json
{
  "success": true,
  "message": "Detection stopped for camera camera1"
}
```

### 4. Get Detection Stats

```http
GET /api/detection/stats
```

**Response:**
```json
{
  "camera1": {
    "url": "0",
    "frame_count": 1234,
    "detection_count": 56,
    "conf_threshold": 0.25,
    "iou_threshold": 0.45
  }
}
```

---

## Frontend Integration (React/Vue)

### 1. WebSocket Connection

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:5000/ws/detections');
const [detections, setDetections] = useState([]);
const [lastDetectionTime, setLastDetectionTime] = useState(0);

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'detections') {
        setDetections(message.data || []);
        setLastDetectionTime(Date.now());
    }
};
```

### 2. Canvas Drawing (React Example)

```jsx
import React, { useRef, useEffect } from 'react';

function VideoStream({ detections, lastDetectionTime }) {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const animationFrameRef = useRef(null);

    const drawDetections = () => {
        const canvas = canvasRef.current;
        const video = videoRef.current;

        if (!canvas || !video) return;

        // Resize canvas to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Check if detections are recent (within 1 second)
        const now = Date.now();
        if (now - lastDetectionTime > 1000) {
            return;
        }

        // Draw each detection
        detections.forEach((detection) => {
            const [x, y, w, h] = detection.bbox;
            const label = `${detection.class} (${(detection.confidence * 100).toFixed(0)}%)`;

            // Draw rectangle
            ctx.strokeStyle = '#00FF00';
            ctx.lineWidth = 3;
            ctx.strokeRect(x, y, w, h);

            // Draw label background
            ctx.font = 'bold 14px Arial';
            const textWidth = ctx.measureText(label).width;
            ctx.fillStyle = '#00FF00';
            ctx.fillRect(x, y - 22, textWidth + 10, 22);

            // Draw label text
            ctx.fillStyle = '#000';
            ctx.fillText(label, x + 5, y - 5);
        });
    };

    useEffect(() => {
        const draw = () => {
            drawDetections();
            animationFrameRef.current = requestAnimationFrame(draw);
        };

        draw();

        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [detections, lastDetectionTime]);

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            />
            <canvas
                ref={canvasRef}
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: 'none'
                }}
            />
        </div>
    );
}
```

### 3. Start/Stop Detection

```javascript
// Start detection
async function startDetection(cameraId, rtspUrl) {
    const response = await fetch(
        `http://localhost:5000/api/detection/start/${cameraId}?rtsp_url=${encodeURIComponent(rtspUrl)}`,
        { method: 'POST' }
    );
    const result = await response.json();
    console.log(result);
}

// Stop detection
async function stopDetection(cameraId) {
    const response = await fetch(
        `http://localhost:5000/api/detection/stop/${cameraId}`,
        { method: 'POST' }
    );
    const result = await response.json();
    console.log(result);
}
```

---

## Detection Format

### Bbox Format

```
[x, y, width, height]
```

- `x`: X coordinate của top-left corner
- `y`: Y coordinate của top-left corner
- `width`: Chiều rộng của bounding box
- `height`: Chiều cao của bounding box

**Ví dụ:**
```json
{
  "class": "license_plate",
  "confidence": 0.95,
  "bbox": [100, 150, 200, 80],  // x=100, y=150, w=200, h=80
  "camera_id": "camera1",
  "frame_id": 123,
  "timestamp": 1234567890.123
}
```

### WebSocket Message Format

```json
{
  "type": "detections",
  "data": [
    {
      "class": "license_plate",
      "confidence": 0.95,
      "bbox": [100, 150, 200, 80],
      "camera_id": "camera1",
      "frame_id": 123,
      "timestamp": 1234567890.123
    }
  ]
}
```

---

## Performance Tuning

### 1. Điều chỉnh Detection Threshold

```python
# Giảm threshold để detect nhiều hơn (nhiều false positives)
conf_threshold = 0.15

# Tăng threshold để chỉ detect khi chắc chắn (ít false positives, có thể miss)
conf_threshold = 0.5
```

### 2. Điều chỉnh FPS

Trong `detection_stream.py`, dòng 160:

```python
# Tăng FPS (giảm sleep time)
time.sleep(0.016)  # ~60 FPS

# Giảm FPS để tiết kiệm CPU
time.sleep(0.1)    # ~10 FPS
```

### 3. Multi-camera Performance

Detection service hỗ trợ nhiều camera cùng lúc:

```bash
# Start camera 1
curl -X POST "http://localhost:5000/api/detection/start/camera1?rtsp_url=0"

# Start camera 2
curl -X POST "http://localhost:5000/api/detection/start/camera2?rtsp_url=1"

# Start RTSP camera
curl -X POST "http://localhost:5000/api/detection/start/parking_lot?rtsp_url=rtsp://..."
```

---

## Troubleshooting

### 1. WebSocket không kết nối

```bash
# Kiểm tra backend đang chạy
curl http://localhost:5000/health

# Kiểm tra WebSocket endpoint
curl http://localhost:5000/docs
```

### 2. Không detect được

- Thử giảm `conf_threshold` xuống `0.15`
- Kiểm tra camera có hoạt động không
- Xem logs trong console

### 3. Camera không mở được

```bash
# Test camera bằng OpenCV
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"

# Test RTSP URL
ffmpeg -i "rtsp://..." -frames:v 1 test.jpg
```

### 4. Latency cao

- Giảm FPS trong detection loop
- Sử dụng GPU nếu có (CUDA)
- Kiểm tra network bandwidth cho RTSP streams

---

## So sánh với parkAI backend-edge1

| Feature | backend-edge1 | camera_IP |
|---------|---------------|-----------|
| **Camera** | IMX500 (RPi) | RTSP / Webcam |
| **Detection** | IMX500 Hardware | YOLOv8 Software |
| **WebSocket** | ✅ | ✅ |
| **Canvas Drawing** | ✅ Frontend | ✅ Frontend |
| **Bbox Format** | `[x, y, w, h]` | `[x, y, w, h]` |
| **OCR** | Async pipeline | Not implemented |
| **Barrier Control** | ✅ | ❌ |

---

## Next Steps

1. **Tích hợp vào frontend chính** (frontend2)
2. **Thêm OCR** để đọc text biển số
3. **Database logging** để lưu lịch sử detections
4. **Alert system** khi detect biển số cụ thể

---

## Files Created

- `websocket_manager.py` - WebSocket connection manager
- `detection_stream.py` - Real-time detection service
- `test_websocket.html` - Test page với canvas drawing
- `main.py` - Updated với WebSocket endpoints

---

**Happy Detecting! 🎯**

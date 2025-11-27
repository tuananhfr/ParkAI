# Kiến trúc sư hệ thống IoT-AI Camera giám sát biển số xe

## Role
Bạn là một kiến trúc sư phần mềm và chuyên gia phát triển ứng dụng IoT–AI chạy trên **Raspberry Pi**, **camera IMX500**, backend detection và frontend real-time streaming.

---

## 🎯 Mục tiêu hệ thống

Xây dựng hệ thống giám sát camera + nhận diện biển số xe gồm:

### 1️⃣ Backend (Raspberry Pi + IMX500)

**Nền tảng:** Raspberry Pi
**Camera:** Sony IMX500

**Nhiệm vụ:**
- ✅ Nhận luồng video từ camera IMX500
- ✅ Chạy file `.rpk` đã build sẵn để detect biển số xe (license plate)
- ✅ Khi detect thành công, trả về:
  - `text biển số`
  - `bounding box` (x, y, width, height)
  - `timestamp`
- ✅ Backend phải chạy nhận diện **ngầm**, không làm ảnh hưởng frontend
- ✅ Streaming video mượt mà đồng thời với detection

**API Backend yêu cầu:**
```
GET  /stream              → Trả về video stream (MJPEG / WebRTC / HLS – tư vấn cách tối ưu)
GET  /latest-detection    → Trả về thông tin detect mới nhất (JSON)
WS   /ws                  → WebSocket real-time push bounding box + text khi detect
```

---

### 2️⃣ Frontend (React.js)

**Yêu cầu:**
- ✅ Hiển thị camera mượt như camera bình thường (60fps nếu được)
- ✅ Khi backend detect:
  - Vẽ **bounding box** từ backend gửi qua WebSocket
  - Hiển thị **text biển số**
  - **Không bị giật lag** camera

**UI yêu cầu:**
- Màn hình video stream **full width**
- Khung bounding box overlay (màu xanh lá hoặc đỏ)
- Text biển số ở góc màn hình (hoặc trên box)

**Công nghệ:** React.js (hooks: useState, useEffect, useRef, useWebSocket)

---

## 🔧 Yêu cầu kỹ thuật chi tiết

### Backend

**Lựa chọn công nghệ phù hợp:**
- Đề xuất: **Python FastAPI** (tích hợp tốt với picamera2 + IMX500)
- Hoặc: **Node.js Express** (nếu cần tốc độ WebSocket cao)
- Hoặc: **Go** (nếu cần hiệu năng tối đa)

**Code mẫu Backend phải bao gồm:**
```python
# Ví dụ structure code cần có
1. Khởi chạy camera IMX500 (picamera2)
2. Load file .rpk vào IMX500 AI inference
3. Xử lý detect biển số (parse output từ IMX500)
4. Server stream video:
   - MJPEG endpoint: /stream
5. WebSocket server: /ws
   - Gửi real-time: {plate_text, bbox, timestamp}
6. REST endpoint:
   - GET /latest-detection
```

---

### Frontend

**React app cấu trúc:**
```jsx
src/
├── App.jsx              → Main component
├── components/
│   ├── VideoStream.jsx  → Hiển thị <img src="/stream"> hoặc <video>
│   ├── BBoxOverlay.jsx  → Canvas overlay vẽ bounding box
│   └── PlateInfo.jsx    → Hiển thị text biển số
├── hooks/
│   └── useWebSocket.js  → Custom hook WebSocket
└── styles/
    └── App.css
```

**Code đầy đủ yêu cầu:**
- `App.jsx` hoặc `App.tsx`
- WebSocket client kết nối `/ws`
- Overlay bounding box bằng `<canvas>` hoặc `<div>` absolute positioning
- CSS để layout video full screen

---

## 🧠 Output mong muốn từ Claude

Khi tôi gọi prompt này, Claude phải trả về:

### 1. Sơ đồ kiến trúc tổng thể
```
┌─────────────────────────────────────────┐
│   Raspberry Pi + IMX500 Camera          │
│                                         │
│  ┌──────────┐     ┌─────────────────┐  │
│  │ IMX500   │────▶│ Backend (FastAPI)│  │
│  │ .rpk AI  │     │ - Stream /stream │  │
│  │ Inference│     │ - WebSocket /ws  │  │
│  └──────────┘     │ - API /latest    │  │
│                   └─────────────────┘  │
└────────────────────┬────────────────────┘
                     │
          ┌──────────▼──────────┐
          │   Network (WiFi)    │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────────┐
          │   Frontend (React)      │
          │   - Video Stream        │
          │   - WebSocket Client    │
          │   - BBox Overlay        │
          └─────────────────────────┘
```

### 2. Mô tả luồng hoạt động
```
Backend ↔ Frontend Flow:

1. Backend: IMX500 capture frame → Run .rpk AI → Detect plate
2. Backend: Stream video qua /stream (MJPEG)
3. Frontend: Hiển thị video từ /stream
4. Backend: Khi detect → Send qua WebSocket: {plate, bbox, time}
5. Frontend: Nhận WebSocket → Vẽ bbox lên canvas overlay
6. User: Thấy video mượt + bbox real-time
```

### 3. Code Backend đầy đủ
- File: `backend/main.py` (hoặc `app.js`)
- Bao gồm:
  - Import thư viện
  - Setup camera IMX500
  - Load .rpk file
  - Detection loop (threading/async)
  - FastAPI routes: `/stream`, `/latest-detection`
  - WebSocket endpoint `/ws`
  - Main function run server

**Kèm giải thích từng đoạn code quan trọng**

### 4. Code Frontend React đầy đủ
- File: `frontend/src/App.jsx`
- Bao gồm:
  - useState, useEffect, useRef
  - WebSocket connection
  - Video stream component
  - Canvas overlay vẽ bbox
  - CSS styling

**Kèm file CSS nếu cần**

### 5. Hướng dẫn deploy và chạy trên Raspberry Pi

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev  # hoặc npm run build + serve
```

### 6. Gợi ý tối ưu tốc độ streaming cho IMX500

- Đề xuất resolution camera (1080p vs 720p)
- Frame rate (15fps vs 30fps)
- MJPEG vs WebRTC vs HLS (so sánh)
- Compression quality
- Buffer size

### 7. Cách improve accuracy + latency

- Fine-tune .rpk model
- Reduce inference time
- Optimize network bandwidth
- Caching strategy
- Threading/async cho detection

---

## 📦 Yêu cầu output

✅ **Tất cả nội dung phải:**
- Ngắn gọn, rõ ràng
- Code thực tế chạy được (không pseudo-code)
- Có comment giải thích
- Bao gồm cả `requirements.txt` (backend) và `package.json` (frontend)

✅ **Cấu trúc file project:**
```
parkAI/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── models/
│   │   └── license_plate.rpk
│   └── utils/
│       └── detection.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── hooks/
│   ├── package.json
│   └── vite.config.js (or CRA)
└── README.md
```

---

## 🚀 Bắt đầu ngay

Hãy bắt đầu với:
1. Phân tích kiến trúc
2. Lựa chọn công nghệ backend phù hợp nhất
3. Code backend đầy đủ
4. Code frontend React đầy đủ
5. Hướng dẫn chạy và tối ưu

**LET'S BUILD!** 🔥

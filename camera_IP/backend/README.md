# Backend API - License Plate Detection

Backend API cho hệ thống quản lý camera và nhận diện biển số xe, sử dụng FastAPI + YOLOv8.

## Tính năng

- **Camera Management**: Quản lý camera RTSP qua REST API
- **License Plate Detection**: Nhận diện biển số xe bằng YOLOv8
- **Real-time Streaming**: Tích hợp với go2rtc để stream video
- **Multiple Detection Modes**: Upload ảnh, RTSP stream, visualize bounding boxes

---

## Yêu cầu hệ thống

- **Python**: 3.8+
- **CUDA** (optional): Để tăng tốc độ inference với GPU
- **go2rtc** (optional): Để stream camera RTSP

---

## Quick Start - Siêu đơn giản!

### Linux/Mac:
```bash
make          # Chỉ cần gõ make, nó tự động làm hết!
```

### Windows:
```bash
make.bat      # Chỉ cần gõ make.bat, nó tự động làm hết!
```

**Xong!** Server sẽ tự động:
1. ✅ Kiểm tra dependencies (nếu thiếu → tự cài)
2. ✅ Kiểm tra model files
3. ✅ Khởi động server tại http://localhost:5000

---

## Cài đặt thủ công (nếu cần)

### Cách 1: Sử dụng Makefile (Khuyến nghị)

```bash
# Cài đặt dependencies + kiểm tra models
make setup

# Hoặc chỉ cài dependencies
make install
```

### Cách 2: Cài đặt thủ công

```bash
# Cài đặt Python packages
pip install -r requirements.txt

# Kiểm tra model files
ls -lh models/
```

---

## Cấu trúc thư mục

```
backend/
├── main.py                      # FastAPI application
├── license_plate_detector.py    # YOLOv8 detector class
├── test_detection.py            # Test script
├── requirements.txt             # Python dependencies
├── Makefile                     # Build automation
├── go2rtc.yaml                  # Camera streams config
├── models/                      # Model files (REQUIRED)
│   ├── license_plate.pt         # YOLOv8 license plate model
│   ├── ocr.onnx                 # OCR model (optional)
│   └── labels.txt               # Class labels
└── README.md                    # This file
```

---

## Chạy server (các cách khác)

### Cách 1: Chỉ cần `make` (Đơn giản nhất - Khuyến nghị!)

```bash
# Linux/Mac
make

# Windows
make.bat
```

### Cách 2: Development mode (auto-reload)

```bash
# Linux/Mac
make dev

# Windows
make.bat dev

# Hoặc thủ công
uvicorn main:app --reload --port 5000
```

### Cách 3: Production mode

```bash
# Linux/Mac
make run

# Windows
make.bat run

# Hoặc thủ công
python main.py
```

### Cách 4: Chạy cùng go2rtc

```bash
make start
# hoặc
npm start
```

Server sẽ chạy tại: **http://localhost:5000**

---

## API Endpoints

### System

```http
GET /health
```
Health check endpoint

### Camera Management

```http
GET    /api/cameras           # Lấy danh sách cameras
POST   /api/cameras           # Thêm camera mới
PUT    /api/cameras/{id}      # Cập nhật camera
DELETE /api/cameras/{id}      # Xóa camera
```

**Example: Thêm camera**
```bash
curl -X POST http://localhost:5000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "id": "camera1",
    "url": "rtsp://admin:password@192.168.1.100:554/stream",
    "name": "Camera Cổng Chính",
    "type": "rtsp"
  }'
```

### License Plate Detection

```http
POST /api/detect/upload           # Detect từ file upload
POST /api/detect/upload/visualize # Detect + vẽ bounding boxes
POST /api/detect/rtsp             # Detect từ RTSP stream
```

**Example: Detect từ file ảnh**
```bash
curl -X POST http://localhost:5000/api/detect/upload \
  -F "file=@car.jpg" \
  -F "conf_threshold=0.25" \
  -F "iou_threshold=0.45"
```

**Response:**
```json
{
  "detections": [
    {
      "bbox": [100, 150, 300, 200],
      "confidence": 0.95,
      "class_id": 0,
      "class_name": "license_plate"
    }
  ],
  "count": 1,
  "processing_time_ms": 45.67
}
```

**Example: Detect + visualize**
```bash
curl -X POST http://localhost:5000/api/detect/upload/visualize \
  -F "file=@car.jpg" \
  -F "conf_threshold=0.25" \
  -F "color_r=0" \
  -F "color_g=255" \
  -F "color_b=0" \
  --output result.jpg
```

**Example: Detect từ RTSP**
```bash
curl -X POST "http://localhost:5000/api/detect/rtsp?rtsp_url=rtsp://admin:password@192.168.1.100:554/stream&conf_threshold=0.3"
```

---

## API Documentation

Sau khi chạy server, truy cập:

- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc

Hoặc sử dụng:
```bash
make docs
```

---

## Testing

### Test detection

```bash
make test
# hoặc
python test_detection.py
```

### Test API endpoints

```bash
# Test health endpoint
make test-health

# Test tất cả endpoints
make test-api
```

### Test bằng curl

```bash
# Health check
curl http://localhost:5000/health

# Lấy danh sách cameras
curl http://localhost:5000/api/cameras
```

---

## Makefile/Batch Commands

### Linux/Mac (Makefile)

```bash
# Quick Start
make               # 🚀 DEFAULT: Auto check deps + run (Khuyến nghị!)
make help          # Hiển thị tất cả commands

# Setup & Installation
make install       # Cài đặt dependencies
make setup         # Cài đặt + kiểm tra models
make check-models  # Kiểm tra file models

# Running
make run           # Chạy production server
make dev           # Chạy development server (auto-reload)
make start         # Chạy cùng go2rtc

# Testing
make test          # Chạy detection tests
make test-health   # Test health endpoint
make test-api      # Test API endpoints

# Maintenance
make clean         # Xóa cache files
make clean-all     # Xóa tất cả generated files

# Information
make info          # Hiển thị system info
make status        # Kiểm tra server status
make show-endpoints # Hiển thị tất cả API endpoints

# Quick Start
make quickstart    # Setup + Run (all-in-one)
```

### Windows (Batch)

```bash
# Quick Start
make.bat           # 🚀 DEFAULT: Auto check deps + run (Khuyến nghị!)
make.bat help      # Hiển thị tất cả commands

# Các lệnh khác tương tự
make.bat install
make.bat run
make.bat dev
make.bat test
make.bat clean
make.bat info
make.bat status
```

---

## Troubleshooting

### 1. Lỗi "Model file not found"

```bash
# Kiểm tra file model
ls -lh models/license_plate.pt

# Đảm bảo file model tồn tại
make check-models
```

### 2. Lỗi "CUDA out of memory"

```python
# Detector sẽ tự động fallback về CPU nếu không có GPU
# Device hiển thị khi khởi động: [DEVICE] Using device: cuda/cpu
```

### 3. Server không khởi động

```bash
# Kiểm tra port 5000 có bị chiếm không
lsof -i :5000

# Hoặc đổi port trong main.py
PORT = 5001
```

### 4. RTSP stream không kết nối được

```bash
# Test RTSP URL bằng ffmpeg
ffmpeg -rtsp_transport tcp -i "rtsp://..." -frames:v 1 test.jpg

# Hoặc VLC media player
vlc rtsp://...
```

### 5. Dependencies lỗi

```bash
# Cài đặt lại dependencies
pip install --upgrade -r requirements.txt

# Kiểm tra version
make info
```

---

## Performance Tips

### 1. Sử dụng GPU

```bash
# Kiểm tra CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Cài đặt PyTorch với CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 2. Tối ưu confidence threshold

- `conf_threshold=0.25`: Mặc định, cân bằng precision/recall
- `conf_threshold=0.5`: Ít false positives, có thể miss một số biển số
- `conf_threshold=0.1`: Nhiều detections, nhưng nhiều false positives

### 3. Tối ưu RTSP streaming

File `go2rtc.yaml` đã được config với các tham số tối ưu:
```yaml
streams:
  camera1: rtsp://...#video=copy#audio=copy
```

---

## Development

### Thêm detector mới

1. Tạo class detector trong file riêng
2. Kế thừa hoặc tương tự `LicensePlateDetector`
3. Thêm endpoints mới trong `main.py`
4. Update `requirements.txt` nếu cần thêm dependencies

### Code structure

```python
# main.py
- FastAPI app setup
- CORS middleware
- Camera management endpoints
- Detection endpoints
- Config management

# license_plate_detector.py
- LicensePlateDetector class
- YOLO model loading
- Detection logic
- Visualization functions
```

---

## Environment Variables

```bash
# Optional: Set custom port
export PORT=5001

# Optional: Set model path
export MODEL_PATH=./custom_models/license_plate.pt
```

---

## Docker (Optional)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "main.py"]
```

```bash
# Build
docker build -t license-plate-api .

# Run
docker run -p 5000:5000 -v $(pwd)/models:/app/models license-plate-api
```

---

## License

[Thêm license của bạn ở đây]

---

## Support

Nếu gặp vấn đề:
1. Kiểm tra logs khi chạy server
2. Chạy `make info` để xem system info
3. Chạy `make check-models` để kiểm tra models
4. Xem API docs tại http://localhost:5000/docs

---

**Generated with Claude Code** 🤖

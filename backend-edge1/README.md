# Backend Edge - Camera AI

Edge backend chạy trên Raspberry Pi 5 với IMX500 AI camera.

## Chức năng

- **Camera AI**: Detect biển số xe bằng IMX500
- **OCR**: Đọc text biển số (YOLO/ONNX)
- **WebRTC**: Stream video realtime
- **Barrier Control**: Điều khiển cửa tự động (GPIO)
- **Central Sync**: Đồng bộ dữ liệu lên server trung tâm
- **SQLite**: Lưu lịch sử local

## Cài đặt & Chạy

```bash
cd backend-edge1
make
```

**Chỉ 1 lệnh!** Makefile tự động:
- Check & cài picamera2, FFmpeg libs (nếu thiếu)
- Tạo venv + cài Python packages
- Chạy app

**Các lệnh khác:**
- `make setup` - Force cài lại từ đầu
- `make run` - Chỉ chạy app
- `make clean` - Xóa cache

## Cấu hình

Sửa `config.py`:

```python
# Camera info
CAMERA_ID = 1
CAMERA_NAME = "Cổng vào A"
CAMERA_TYPE = "ENTRY"  # hoặc "EXIT"

# Central server
CENTRAL_SERVER_URL = "http://192.168.0.144:8000"

# OCR
ONNX_OCR_MODEL_PATH = "/path/to/ocr.onnx"
```

## API

- `GET /api/status` - Trạng thái server
- `POST /offer` - WebRTC video stream
- `WS /ws/detections` - WebSocket detections
- `POST /api/open-barrier` - Mở cửa

## Troubleshooting

**Lỗi dependencies:**
```bash
make setup  # Cài lại tất cả
```

**Camera không detect:**
```bash
libcamera-hello --list-cameras
sudo reboot
```

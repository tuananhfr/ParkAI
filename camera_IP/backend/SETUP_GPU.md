# Setup GPU cho Production

Hướng dẫn setup backend để sử dụng GPU NVIDIA cho xử lý nhiều camera.

## Kiến trúc GPU Batch Processing

```
Camera 1 ──┐
Camera 2 ──┼──> Frame Queue ──> GPU Batch Inference ──> Results ──> WebSocket
Camera 3 ──┤    (Buffer)         (Parallel Processing)
Camera 4 ──┘
```

**Ưu điểm:**
- Tận dụng 80-95% GPU (thay vì 20-30% với threading)
- Throughput tăng 3-4x so với xử lý tuần tự
- Tự động điều chỉnh batch size theo GPU
- Hỗ trợ 1-8 cameras mượt mà

---

## Yêu cầu

### Hardware
- **GPU NVIDIA** với CUDA support (GeForce GTX 1050 trở lên)
- **VRAM:** Tối thiểu 4GB (khuyến nghị 6GB+)
- **RAM:** 8GB+
- **CPU:** 4 cores+

### Software
- **Windows 10/11** hoặc **Linux** (Ubuntu 20.04+)
- **Python 3.8+**
- **CUDA Toolkit 11.8** hoặc **12.1**
- **cuDNN 8.x**

---

## Cài đặt

### Bước 1: Cài CUDA Toolkit

#### Windows:
1. Download CUDA Toolkit từ: https://developer.nvidia.com/cuda-downloads
2. Chọn phiên bản **CUDA 11.8** (khuyến nghị) hoặc **12.1**
3. Cài đặt với tùy chọn mặc định
4. Verify: Mở CMD, chạy `nvcc --version`

#### Linux:
```bash
# Ubuntu 20.04/22.04
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run
sudo sh cuda_11.8.0_520.61.05_linux.run

# Verify
nvcc --version
nvidia-smi
```

### Bước 2: Cài cuDNN (Optional nhưng khuyến nghị)

1. Download từ: https://developer.nvidia.com/cudnn
2. Extract và copy files vào thư mục CUDA
3. Verify: `python -c "import torch; print(torch.backends.cudnn.enabled)"`

### Bước 3: Cài đặt Python dependencies

#### Với GPU (CUDA 11.8):
```bash
cd backend
pip install -r requirements-gpu.txt
```

#### Với GPU (CUDA 12.1):
```bash
# Sửa file requirements-gpu.txt: cu118 -> cu121
pip install -r requirements-gpu.txt
```

#### Verify GPU hoạt động:
```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
```

Kết quả mong đợi:
```
CUDA available: True
GPU: NVIDIA GeForce RTX 3080
```

---

## Cấu hình

### Tùy chỉnh batch size theo GPU

Sửa file `gpu_config.yaml`:

```yaml
gpu:
  # Auto-detect batch size (khuyến nghị)
  batch_size: auto

  # Hoặc set manual theo GPU:
  # RTX 4090 (24GB): batch_size: 16
  # RTX 3080 (12GB): batch_size: 8
  # RTX 3070 (8GB):  batch_size: 6
  # RTX 3060 (6GB):  batch_size: 4
  # GTX 1660 (4GB):  batch_size: 2

  # Input size (640 = standard, 1280 = high quality, 480 = fast)
  input_size: 640

  # FP16 (half precision) - nhanh hơn 2x trên RTX 20xx+
  fp16: false  # Set true nếu GPU hỗ trợ Tensor Cores
```

### Bật GPU Batch Processing

Trong file `main.py`, đảm bảo:

```python
USE_GPU_BATCH = True  # Sử dụng GPU batch processing
```

---

## Chạy Backend

### Development (máy không có GPU):
```bash
# Dùng CPU
python main.py
```

### Production (máy có GPU):
```bash
# Dùng GPU với batch processing
python main.py
```

Server sẽ tự động detect GPU và hiển thị:
```
[DEVICE] Using device: cuda
[GPU] NVIDIA GeForce RTX 3080 - 10.0GB VRAM
[GPU BATCH] Initialized with device=cuda, batch_size=8
[MAIN] Using GPU Batch Detection Service (optimized for 1-8 cameras)
```

---

## API Endpoints

### Start detection cho camera:
```bash
POST http://localhost:5000/api/detection/start/camera1
{
  "rtsp_url": "rtsp://192.168.1.100:554/stream",
  "conf_threshold": 0.25,
  "iou_threshold": 0.45
}
```

### Stop detection:
```bash
POST http://localhost:5000/api/detection/stop/camera1
```

### Xem statistics:
```bash
GET http://localhost:5000/api/detection/stats
```

Response:
```json
{
  "cameras": {
    "camera1": {
      "url": "rtsp://...",
      "frame_count": 1234,
      "detection_count": 56
    }
  },
  "global": {
    "device": "cuda",
    "batch_size": 8,
    "total_frames": 1234,
    "total_detections": 56,
    "avg_batch_size": 6.5,
    "avg_inference_time_ms": 45.2,
    "frame_queue_size": 12,
    "result_queue_size": 3
  }
}
```

---

## Performance Tuning

### GPU memory hết (OOM):
- Giảm `batch_size` trong `gpu_config.yaml`
- Giảm `input_size` từ 640 xuống 480
- Tăng `frame_skip` để bỏ qua một số frames

### Latency cao:
- Giảm `batch_timeout_ms` trong config
- Giảm `max_queue_size`
- Tăng `frame_skip`

### GPU utilization thấp (<50%):
- Tăng `batch_size`
- Giảm `batch_timeout_ms`
- Thêm cameras (GPU chưa đạt max throughput)

### Monitor GPU:
```bash
# Windows/Linux
nvidia-smi -l 1  # Update every 1 second

# Xem GPU utilization, memory usage, temperature
```

---

## So sánh Performance

| Cấu hình | FPS/camera | GPU Utilization | Latency |
|----------|------------|-----------------|---------|
| Threading (CPU) | 10-15 | 0% | 100-200ms |
| Threading (GPU) | 15-20 | 20-30% | 80-150ms |
| **Batch (GPU)** | **25-30** | **80-95%** | **50-100ms** |

**Throughput tăng 2-3x** với GPU Batch Processing!

---

## Troubleshooting

### Lỗi: `CUDA out of memory`
```python
# Giảm batch size trong gpu_config.yaml
batch_size: 4  # Giảm từ 8 xuống 4
```

### Lỗi: `CUDA not available`
```bash
# Verify CUDA installation
nvcc --version
nvidia-smi

# Reinstall PyTorch with CUDA
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Lỗi: `RuntimeError: Expected all tensors to be on the same device`
```python
# Model và data không cùng device
# Code đã tự động handle, nếu gặp lỗi này báo ngay
```

---

## Deploy lên máy Production

### Transfer code từ máy dev sang máy GPU:

1. **Copy toàn bộ folder backend**:
```bash
# Trên máy dev
zip -r backend.zip backend/

# Transfer sang máy GPU (qua USB, network, etc.)
```

2. **Setup trên máy GPU**:
```bash
# Cài CUDA + cuDNN (xem Bước 1, 2 ở trên)

# Cài dependencies
cd backend
pip install -r requirements-gpu.txt

# Copy model files
# Đảm bảo có file: models/license_plate.pt
```

3. **Chạy**:
```bash
python main.py
```

4. **Test**:
```bash
# Từ máy khác hoặc máy dev
curl http://GPU_MACHINE_IP:5000/health
```

---

## Best Practices

1. **Luôn dùng auto batch size** - service sẽ tự điều chỉnh theo GPU
2. **Monitor GPU temperature** - giữ dưới 85°C
3. **Enable FP16** nếu GPU là RTX 20xx, 30xx, 40xx (nhanh hơn 2x)
4. **Sử dụng SSD** cho models - giảm load time
5. **Đặt server gần cameras** - giảm RTSP latency

---

## Liên hệ

Nếu có vấn đề khi setup GPU, check log output và báo lỗi cụ thể!

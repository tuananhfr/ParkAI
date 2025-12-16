# 🚀 Production Mode - Vehicle Tracking Guide

## Tổng quan

Hệ thống đã được nâng cấp lên **Production-grade** với ByteTrack vehicle tracking và state machine.

### ✅ Tính năng mới

| Feature | Legacy Mode | Production Mode |
|---------|-------------|-----------------|
| **Tracking** | ❌ Theo bbox (mất votes khi xe di chuyển) | ✅ Theo vehicle_id (giữ votes khi xe di chuyển) |
| **Multi-vehicle** | ❌ Xử lý tuần tự, 1 xe/lần | ✅ Track đồng thời nhiều xe |
| **State Machine** | ❌ Không có | ✅ ENTER→MOVING→STOPPED→LEAVING→DONE |
| **ROI** | ❌ Toàn frame | ✅ ROI per camera type |
| **Voting** | ✅ Có nhưng dễ mất votes | ✅ Voting theo vehicle, không mất votes |
| **Chốt biển** | ❌ Khi OCR xong | ✅ Khi vehicle LEAVING (chính xác hơn) |

---

## 📦 Cài đặt

### 1. Cài dependencies

```bash
cd backend-edge1
make install  # hoặc pip install -r requirements.txt
```

Dependencies mới:
- `supervision==0.16.0` - ByteTrack tracking

### 2. Cấu hình trong `config.py`

```python
# BẬT vehicle tracking (default = True)
VEHICLE_TRACKING_ENABLED = True

# Tracking parameters
VEHICLE_TRACK_THRESH = 0.5       # Confidence threshold
VEHICLE_MATCH_THRESH = 0.8       # IOU matching threshold
VEHICLE_STOPPED_THRESHOLD = 5.0  # pixels
VEHICLE_STOPPED_DURATION = 0.5   # seconds

# ROI cho từng loại camera
CAMERA_TYPE = "PARKING_LOT"  # "ENTRY" | "EXIT" | "PARKING_LOT"

# ROI polygon (None = toàn bộ frame)
ROI_ENTRY = None
ROI_EXIT = None
ROI_PARKING_LOT = None

# Ví dụ: Define ROI cho parking lot
# ROI_PARKING_LOT = [
#     (100, 100),   # Top-left
#     (1180, 100),  # Top-right
#     (1180, 620),  # Bottom-right
#     (100, 620)    # Bottom-left
# ]
```

### 3. Chạy hệ thống

```bash
python main.py
```

Hệ thống tự động detect mode:
- ✅ `VEHICLE_TRACKING_ENABLED = True` → **Production Mode**
- ❌ `VEHICLE_TRACKING_ENABLED = False` → Legacy Mode

---

## 🎯 Cách hoạt động

### Production Mode Pipeline

```
Video Frame
    ↓
IMX500 Detection (YOLO)
    ↓
ByteTrack Tracking (gán vehicle_id)
    ↓
State Machine Update
    ├─ ENTER (xe mới xuất hiện)
    ├─ MOVING (xe đang di chuyển)
    ├─ STOPPED (xe đứng yên → OCR liên tục)
    ├─ LEAVING (xe rời ROI → chốt biển)
    └─ DONE (cleanup)
    ↓
OCR per Vehicle (theo vehicle_id)
    ↓
Plate Voting (theo vehicle_id, không mất votes)
    ↓
Finalize Plate (khi LEAVING hoặc đủ votes)
    ↓
Save to DB (1 lần duy nhất)
    ↓
Broadcast to Frontend (với vehicle_id + state)
```

### Ví dụ: 3 xe đỗ trong parking lot

**Production Mode:**
```
T=0s:
  - Xe A, B, C xuất hiện → Track với ID 1, 2, 3
  - State: ENTER → MOVING

T=0.5s:
  - 3 xe đứng yên → State: STOPPED
  - OCR cả 3 xe đồng thời
  - Vehicle #1: OCR "51N12345" → Vote 1
  - Vehicle #2: OCR "51N67890" → Vote 1
  - Vehicle #3: OCR "51N11111" → Vote 1

T=1s:
  - 3 xe vẫn STOPPED
  - OCR tiếp
  - Vehicle #1: OCR "51N12345" → Vote 2 → FINALIZED ✅
  - Vehicle #2: OCR "51N67890" → Vote 2 → FINALIZED ✅
  - Vehicle #3: OCR "51N11111" → Vote 2 → FINALIZED ✅

KẾT QUẢ: 3 xe được xử lý trong 1 giây! 🚀
```

**Legacy Mode (cũ):**
```
T=0s: Capture xe A
T=0.5s: OCR xe A
T=2.5s: Cooldown xong → Capture xe B
T=3s: OCR xe B
T=5s: Cooldown xong → Capture xe C
T=5.5s: OCR xe C

KẾT QUẢ: 3 xe mất 5.5 giây 🐌
```

---

## 🔧 Cấu hình cho 3 loại camera

### 1. ENTRY Camera (Cổng vào)

```python
CAMERA_TYPE = "ENTRY"
ROI_ENTRY = None  # Toàn frame hoặc define polygon cụ thể

# Logic:
# - Xe ENTER → MOVING → STOPPED (chờ ở cổng)
# - OCR liên tục khi STOPPED
# - Finalize khi rời ROI (đi vào bãi)
```

### 2. EXIT Camera (Cổng ra)

```python
CAMERA_TYPE = "EXIT"
ROI_EXIT = None

# Logic:
# - Xe ENTER → MOVING → STOPPED (chờ thanh toán)
# - OCR liên tục
# - Finalize khi rời ROI (ra khỏi bãi)
```

### 3. PARKING_LOT Camera (Bãi đỗ xe)

```python
CAMERA_TYPE = "PARKING_LOT"
ROI_PARKING_LOT = [
    (100, 100), (1180, 100),
    (1180, 620), (100, 620)
]

# Logic:
# - Xe ENTER → MOVING → STOPPED (đỗ xe)
# - OCR liên tục khi STOPPED
# - Track xe đỗ lâu (update location)
# - Finalize khi rời ROI
```

---

## 🧪 Testing

### Test 1: Xe đơn lẻ

1. Đặt 1 xe vào frame
2. Quan sát frontend:
   - Thấy box với `vehicle_id` và `state`
   - State: ENTER → MOVING → STOPPED
   - Plate text xuất hiện khi đủ votes
   - `finalized: true` khi chốt

### Test 2: 3 xe cùng lúc (PARKING_LOT)

1. Đặt 3 xe vào frame
2. Quan sát:
   - 3 boxes với 3 `vehicle_id` khác nhau
   - Cả 3 xe được OCR đồng thời
   - 3 plates được finalize nhanh (~1-2s)
3. Check DB: 3 records mới

### Test 3: Xe di chuyển (ENTRY/EXIT)

1. Xe đi từ ngoài vào ROI
2. Quan sát:
   - State: ENTER → MOVING
   - OCR chạy thỉnh thoảng
3. Xe dừng lại
   - State: STOPPED
   - OCR liên tục
   - Plate finalized
4. Xe rời ROI
   - State: LEAVING → DONE
   - DB saved

---

## 🐛 Troubleshooting

### Vấn đề 1: Không track được xe

**Nguyên nhân:** Confidence quá thấp

**Giải pháp:**
```python
VEHICLE_TRACK_THRESH = 0.3  # Giảm threshold
```

### Vấn đề 2: Xe bị mất tracking (ID thay đổi)

**Nguyên nhân:** IOU matching quá cao

**Giải pháp:**
```python
VEHICLE_MATCH_THRESH = 0.6  # Giảm từ 0.8 xuống 0.6
```

### Vấn đề 3: Không chốt được biển

**Nguyên nhân:** Xe rời ROI quá nhanh, chưa đủ votes

**Giải pháp:**
```python
PLATE_MIN_VOTES = 1  # Giảm từ 2 xuống 1 (trade-off: kém chính xác)
```

### Vấn đề 4: Muốn dùng Legacy Mode

**Giải pháp:**
```python
VEHICLE_TRACKING_ENABLED = False  # Tắt production mode
```

---

## 📊 Performance

### Legacy Mode vs Production Mode

| Metric | Legacy | Production |
|--------|--------|------------|
| **3 xe đỗ** | 5.5s | 1-2s ⚡ |
| **CPU usage** | ~40% | ~45% (ByteTrack ~5%) |
| **Accuracy** | Mất votes do bbox thay đổi | Giữ votes, chính xác hơn ✅ |
| **Multi-vehicle** | Tuần tự | Đồng thời ✅ |
| **Spam DB** | Có (mỗi 15s lưu lại) | Không (chỉ lưu khi LEAVING) ✅ |

---

## 🎓 Best Practices

### 1. ROI Setup

- **ENTRY/EXIT**: ROI bao phủ vùng cổng, tránh xe ngoài đường
- **PARKING_LOT**: ROI chỉ bao vùng đỗ xe, loại bỏ lối đi

### 2. Voting Parameters

```python
# Cho xe dừng lâu (PARKING_LOT)
PLATE_VOTE_WINDOW = 1.5  # Tăng lên 1.5s
PLATE_MIN_VOTES = 3      # Yêu cầu 3 votes (chính xác hơn)

# Cho xe đi nhanh (ENTRY/EXIT)
PLATE_VOTE_WINDOW = 0.8  # Giảm xuống 0.8s
PLATE_MIN_VOTES = 2      # 2 votes là đủ
```

### 3. State Thresholds

```python
# Xe di chuyển chậm
VEHICLE_STOPPED_THRESHOLD = 10.0  # Tăng lên 10px

# Xe di chuyển nhanh
VEHICLE_STOPPED_THRESHOLD = 3.0   # Giảm xuống 3px
```

---

## 📝 API Changes

### Frontend WebSocket Message Format

**Trước (Legacy):**
```json
{
  "type": "detections",
  "data": [{
    "class": "license_plate",
    "confidence": 0.8,
    "bbox": [100, 100, 200, 80],
    "text": "51N12345"
  }]
}
```

**Sau (Production):**
```json
{
  "type": "detections",
  "data": [{
    "class": "license_plate",
    "confidence": 0.8,
    "bbox": [100, 100, 200, 80],
    "text": "51N12345",
    "vehicle_id": 42,           // MỚI: ID của xe
    "state": "STOPPED",         // MỚI: State của xe
    "finalized": true           // MỚI: Đã chốt biển chưa
  }]
}
```

---

## 🚀 Next Steps

1. ✅ Test với 3 xe trong parking lot
2. ⏳ Fine-tune tracking parameters
3. ⏳ Implement vehicle tracking visualization (vẽ ID + state lên frontend)
4. ⏳ Add analytics (vehicle dwell time, traffic flow)

---

## 📞 Support

Nếu có vấn đề, check:
1. Log file: `backend-edge1/logs/`
2. Config: `backend-edge1/config.py`
3. Disable production mode: `VEHICLE_TRACKING_ENABLED = False`

---

**Happy Tracking! 🎉**

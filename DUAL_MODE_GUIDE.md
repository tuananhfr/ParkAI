# Dual-Mode: 1 Camera cho cả VÀO và RA

## ❓ Vấn Đề

Bạn có **1 camera vật lý** nhưng muốn xử lý **cả VÀO lẫn RA**.

❌ **Không thể**: Chạy 2 backend trên 1 Pi (conflict IMX500)

✅ **Giải pháp**: 1 Backend, Frontend có **2 nút** (VÀO/RA), user chọn

---

## 🎯 UI Mong Muốn

```
┌──────────────────────────┐
│ Video + OCR auto-fill    │
├──────────────────────────┤
│ Biển số: 30G56789        │
│                          │
│ [Mở cửa VÀO]  ← Green    │
│ [Mở cửa RA]   ← Red      │
└──────────────────────────┘
```

User quyết định: Xe này VÀO hay RA?

---

## 🔧 Implementation

### 1. Backend: Add `action` parameter

File: `backend2/app.py`

Trong endpoint `/api/open-barrier`, thêm:

```python
action = data.get('action', 'ENTRY')  # NEW: "ENTRY" hoặc "EXIT"

# Gửi event với action này
if central_sync:
    central_sync.send_event(action, {...})
```

### 2. Frontend: 2 Buttons

File: `frontend/src/App1.jsx`

**Thay thế nút cũ**:
```jsx
// CŨ:
<button className="btn btn-success" onClick={handleOpenBarrier}>
  Mở cửa VÀO
</button>

// MỚI:
<div className="d-grid gap-2">
  <button
    className="btn btn-success"
    onClick={() => handleOpenBarrier("ENTRY")}
    disabled={!plateText.trim()}
  >
    <i className="bi bi-door-open-fill me-2"></i>
    Mở cửa VÀO
  </button>

  <button
    className="btn btn-danger"
    onClick={() => handleOpenBarrier("EXIT")}
    disabled={!plateText.trim()}
  >
    <i className="bi bi-door-open-fill me-2"></i>
    Mở cửa RA
  </button>
</div>
```

**Update handler**:
```jsx
const handleOpenBarrier = async (action) => {
  // action = "ENTRY" hoặc "EXIT"

  const response = await fetch(`${backendUrl}/api/open-barrier`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plate_text: plateText,
      confidence: plateConfidence,
      source: plateSource || "manual",
      action: action  // GỬI action
    }),
  });

  // ... xử lý response
};
```

---

## 📡 Central Server Nhận Gì?

### User nhấn VÀO:
```json
POST /api/edge/event
{
  "type": "ENTRY",
  "camera_id": 1,
  "camera_name": "Gate A",
  "data": {
    "plate_text": "30G56789",
    "action": "ENTRY"
  }
}
```

### User nhấn RA:
```json
POST /api/edge/event
{
  "type": "EXIT",
  "camera_id": 1,
  "camera_name": "Gate A",
  "data": {
    "plate_text": "30G56789",
    "action": "EXIT"
  }
}
```

Central xử lý bình thường!

---

## ✅ Ưu Điểm

✅ Chỉ 1 backend (không conflict camera)
✅ User kiểm soát VÀO/RA (chính xác hơn)
✅ Đơn giản, dễ maintain
✅ Central server không cần thay đổi

---

## 🚀 Test

1. Start backend: `python3 app.py`
2. Refresh frontend
3. OCR scan → auto-fill biển số
4. Nhấn **"Mở cửa VÀO"** hoặc **"Mở cửa RA"**
5. Check Central Dashboard thấy event

Done! 🎉
